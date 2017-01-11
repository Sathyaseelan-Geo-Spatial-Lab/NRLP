# -*- coding: utf-8 -*-
"""
Created on Wed Feb 10 12:40:08 2016

@author: Stephanie Higgins
"""

from __future__ import division
import py2neo
import csv
import numpy as np
import argparse

parser=argparse.ArgumentParser()
parser.add_argument("--canals", help="canals can be ON or OFF, optional argument to overwrite input file and turn all canals on or off. Without setting this option, the program uses what is in the input file.")
args = parser.parse_args()

##########################################
############## USER SET-UP ###############
##########################################

#These are points of interest for which we will calculate flow changes.
mouths=['Hooghly mouth','Farakka Barrage','Hardinge Bridge','Bahadurabad Station','Ganga mouth','Mahanadi mouth','Godavari mouth','Krishna mouth','Penna mouth','Kaveri mouth']

##########################################
##########################################
##########################################

riversFile=r'rivers.txt'
linksFile=r'links.txt'
structuresFile=r'structures.txt'
resultsFile=r'results.txt'

##########################################
##########################################
##########################################

def pointname2varname(pointname):
    varname=pointname.upper().replace (" ", "_").replace ("-", "_")
    return varname

# set up authentication parameters
database="localhost:7474"
username="neo4j"
password="database"
py2neo.authenticate(database, username, password)

# connect to authenticated graph database
graph=py2neo.Graph("http://"+database+"/db/data/")
cypher=graph.cypher

#Delete everything in graph... it will be rebuilt each time
cypher.execute('MATCH (n) DETACH DELETE (n)')
   
#Import lines list and generate paths (waterways). 
with open(riversFile, 'rU') as csvfile:
    csvreader = csv.reader(csvfile,delimiter=';')
    pointslist=[]
  #  next(csvreader, None)  # skip the headers
    for row in csvreader:
        #first, find all unique nodes
        rivername=row[0]
        goes_through=row[1]
        goes_points=goes_through.split(',')
        for pointname in goes_points:
            pointnameUF=pointname2varname(pointname)
            if pointnameUF not in pointslist:
                pointslist.append(pointnameUF)
                if 'HEADWATERS' in pointnameUF:
                    pointtype='headwaters'
                elif 'MOUTH' in pointnameUF:
                    pointtype='mouth'
                else:
                    pointtype='confluence'
                
                #Generate Node:
                point = py2neo.Node('point',pointtype,'Exists',name=pointname)
                exec(pointnameUF+" = point")
                graph.create(point)
                
#Farakka is a special case, since it is a permanent part of the existing river network despite being a structure.
cypher.execute('MATCH (n {name:\'Farakka Barrage\'}) SET n :Barrage RETURN n')
cypher.execute('MATCH (n {name:\'Farakka Barrage\'}) SET n.storage=0 RETURN n')

with open(riversFile, 'rU') as csvfile:
    csvreader = csv.reader(csvfile,delimiter=';')
    for row in csvreader:
        #then, create rivers
        rivername=row[0]
        print 'Building '+rivername+' River...'
        goes_through=row[1]
        goes_points=goes_through.split(',')
        start_at_v=pointname2varname(goes_points[0])
        del goes_points[0]
        for point in goes_points:
            end_at_v=pointname2varname(point)
            exec('graph.create(py2neo.rel('+start_at_v+',\"'+rivername+'\",'+end_at_v+',type=\"river\"))')
            start_at_v=end_at_v

graph.push()

#First, figure out which nodes need to be added to build the requested links:
userlist=[]
with open(linksFile, 'rU') as csvfile:
    csvreader = csv.reader(csvfile,delimiter=';')
    next(csvreader, None)  # skip the headers
    next(csvreader, None)  # skip the headers
    for row in csvreader:
        #then, create rivers
        onoff=row[0]
        if (onoff=='ON' or args.canals=='ON') and args.canals !='OFF':
            starts_at_v=pointname2varname(row[2])
            ends_at_v=pointname2varname(row[3])
            other_structure=pointname2varname(row[10])
            if starts_at_v not in pointslist:
                userlist.append(starts_at_v)
            if ends_at_v not in pointslist:
                userlist.append(ends_at_v)
            if other_structure not in pointslist and other_structure != '':
                userlist.append(other_structure)

#First, build a dictionary of upstream and downstream locations to be accessed later 
bigtable=[]
with open(structuresFile, 'rU') as csvfile:
    csvreader = csv.reader(csvfile,delimiter=',')
    next(csvreader, None)  # skip the headers
    for row in csvreader:
        structurename=row[0]
        structurenameUF=pointname2varname(structurename)
        upstream=row[2]
        upstreamUF=pointname2varname(upstream)
        downstream=row[3]
        downstreamUF=pointname2varname(downstream)    
        bigtable.append([structurenameUF,upstreamUF,downstreamUF,upstream,downstream])

#Next, build all of the nodes we need for the user's requested canal. 
with open(structuresFile, 'rU') as csvfile:
    csvreader = csv.reader(csvfile,delimiter=',')
    next(csvreader, None)  # skip the headers
    counter=0
    for row in csvreader:
        structurename=row[0]
        structurenameUF=pointname2varname(structurename)
        if structurenameUF in userlist and structurenameUF not in pointslist:
            rivername=row[1]
            upstream=row[2]
            upstreamUF=pointname2varname(upstream)
            downstream=row[3]
            downstreamUF=pointname2varname(downstream)
            
            #here we do the tricky thing...
            n=1
            while upstreamUF not in pointslist and upstreamUF not in userlist:
                upstreamUF=bigtable[counter-n][1]
                n+=1
            n=1
            while downstreamUF not in pointslist and downstreamUF not in userlist:
                downstreamUF=bigtable[counter-n][2]
                n+=1
                
            storage=row[4]
            existence=row[5]
            pointtype=row[6]
            rivernameUF=pointname2varname(rivername)
            #Create the points if they do not exist
            point = py2neo.Node('point',pointtype,existence,name=structurename,deadstorage=storage)
            exec(structurenameUF+" = point")
            graph.create(point)
            pointslist.append(structurenameUF) #record that the point is constructed
        counter+=1
            
                    
#Yamuna-Rajasthan outfall is a special case because it is just a canal connection, it's not on a river
YRname='Yamuna-Rajasthan Outfall'
YRnameUF=pointname2varname(YRname)
if YRnameUF in userlist:
    point = py2neo.Node('point','Outfall','Proposed',name=YRname)
    exec(YRnameUF+" = point")
    graph.create(point)
    pointslist.append(YRnameUF)
    
#The nodes are there, now go back through the file and build the relationships to put the nodes where they go on rivers.
with open(structuresFile, 'rU') as csvfile:
    csvreader = csv.reader(csvfile,delimiter=',')
    next(csvreader, None)  # skip the headers
    counter=0
    for row in csvreader:
        structurename=row[0]
        structurenameUF=pointname2varname(structurename)
        if structurenameUF in pointslist:
            rivername=row[1]
            upstream=row[2]
            upstreamUF=pointname2varname(upstream)
            downstream=row[3]
            downstreamUF=pointname2varname(downstream)

            #here we do the tricky thing...
            n=1
            while upstreamUF not in pointslist:
                upstreamUF=bigtable[counter-n][1]
                upstream=bigtable[counter-n][3]
                n+=1
            n=1
            while downstreamUF not in pointslist:
                downstreamUF=bigtable[counter-n][2]
                downstream=bigtable[counter-n][4]
                n+=1
                
            #break the relationship between upstream and downstream nodes.
            cypher.execute('MATCH (n {name:\''+upstream+'\'})-[rel]->(a {name:\''+downstream+'\'}) DELETE rel')
            
            #insert this node
            exec('graph.create(py2neo.rel('+structurenameUF+',\"'+rivername+'\",'+downstreamUF+',type=\"river\"))')
            exec('graph.create(py2neo.rel('+upstreamUF+',\"'+rivername+'\",'+structurenameUF+',type=\"river\"))')
            
        counter+=1

#Finally, build the canals
with open(linksFile, 'rU') as csvfile:
    csvreader = csv.reader(csvfile,delimiter=';')
    next(csvreader, None)  # skip the headers
    next(csvreader, None)  # skip the headers
    for row in csvreader:
        #then, create rivers
        onoff=row[0]
        if (onoff=='ON' or args.canals=='ON') and args.canals !='OFF':
            linkname=row[1]
            print 'Building Link '+linkname
            starts_at_v=pointname2varname(row[2])
            ends_at_v=pointname2varname(row[3])
            other_structure=row[10]
            if row[2] not in userlist:
                userlist.append(row[2])
            if row[3] not in userlist:
                userlist.append(row[3])
            if other_structure not in userlist and other_structure != '':
                userlist.append(other_structure)
            monthly=row[9]
            monthlies=monthly.split(',')
            exec('graph.create(py2neo.rel('+starts_at_v+',\"'+linkname+'\",'+ends_at_v+',type=\"canal\",transfer='+row[4]+',TL='+row[5]+',IRR='+row[6]+',DI='+row[7]+',outfall='+row[8]+',Jan='+monthlies[0]+',Feb='+monthlies[1]+',Mar='+monthlies[2]+',Apr='+monthlies[3]+',May='+monthlies[4]+',Jun='+monthlies[5]+',Jul='+monthlies[6]+',Aug='+monthlies[7]+',Sep='+monthlies[8]+',Oct='+monthlies[9]+',Nov='+monthlies[10]+',Dec='+monthlies[10]+',DamTransfer=\''+row[11]+'\'))')
       
# graph.push()

##########################################################################
################ CALCULATE RIVER DISCHARGE CHANGES
##########################################################################

#1. Move the water through the graph one iteration: all transfers (pulls) are negatives for the nodes, and all outfalls are positives.
print 'Calculating river discharge changes...'
p=cypher.execute('MATCH (n) RETURN (n)')
for node in p:

    starting_water=0
    water_monthly=np.array([0.,0,0,0,0,0,0,0,0,0,0,0])
    month_names=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
    nodename=node[0].properties['name']
           
    incanals=cypher.execute('MATCH ()-[r]->(n {name:\''+nodename+'\'}) WHERE r.type=\'canal\' RETURN r')
    for canal in incanals:
        water_monthly+=canal[0].properties['outfall']*np.array([canal[0].properties['Jan'],canal[0].properties['Feb'],canal[0].properties['Mar'],canal[0].properties['Apr'],canal[0].properties['May'],canal[0].properties['Jun'],canal[0].properties['Jul'],canal[0].properties['Aug'],canal[0].properties['Sep'],canal[0].properties['Oct'],canal[0].properties['Nov'],canal[0].properties['Dec']])
        starting_water+=canal[0].properties['outfall']
    
    outcanals=cypher.execute('MATCH ()<-[r]-(n {name:\''+nodename+'\'}) WHERE r.type=\'canal\' RETURN r')
    for canal in outcanals:
        if canal[0].properties['DamTransfer']=='T':
            water_monthly-=canal[0].properties['transfer']*np.array([canal[0].properties['Jan'],canal[0].properties['Feb'],canal[0].properties['Mar'],canal[0].properties['Apr'],canal[0].properties['May'],canal[0].properties['Jun'],canal[0].properties['Jul'],canal[0].properties['Aug'],canal[0].properties['Sep'],canal[0].properties['Oct'],canal[0].properties['Nov'],canal[0].properties['Dec']])         
        if canal[0].properties['DamTransfer']=='K': #special case for Krishna impoundments
            a=np.array([.05,.05,.05,.05,.05,.05,.05,.21,.19,.15,.05,.05]) #If it's a dam, impound annual total during the four monsoon months.
            water_monthly-=a*canal[0].properties['transfer'] 
        if canal[0].properties['DamTransfer']=='D': #all other dams impound during the monsoon
            a=np.array([0,0,0,0,0,0,.27,.313333,.313333,.08333333,.02,0])
            water_monthly-=a*canal[0].properties['transfer'] 
                         
        starting_water-=canal[0].properties['transfer']     
    cypher.execute('MATCH (n {name:\''+nodename+'\'}) SET n.water_shift = '+str(starting_water)+' RETURN n')
    counter=0
    for month in month_names:
        cypher.execute('MATCH (n {name:\''+nodename+'\'}) SET n.'+month+' = '+str(water_monthly[counter])+' RETURN n')
        counter+=1

#2. Turn the canals off: the water has been moved, they are not operating anymore. 
with open(linksFile, 'rU') as csvfile:
        csvreader = csv.reader(csvfile,delimiter=';')
        next(csvreader, None)  # skip the headers
        next(csvreader, None)  # skip the headers
        for row in csvreader:
            #then, create rivers
            onoff=row[0]
            if (onoff=='ON' or args.canals=='ON') and args.canals !='OFF':
                linkname=row[1]
                starts_at=row[2]
                ends_at=row[3]
                cypher.execute('MATCH (n {name:\''+starts_at+'\'})-[rel]->(a {name:\''+ends_at+'\'}) DELETE rel')
     
#2b. As a special case, also turn the Hooghly River off temporarily - it acts as a distributary channel and so shouldn't
  #   receive summed values from the Ganga basin
     
cypher.execute('MATCH (n {name:\''+'Farakka Barrage'+'\'})-[rel]->(a {name:\''+'Hooghly mouth'+'\'}) DELETE rel')  
        
#3. Sum over all the paths to the mouth of interest. Include the dams here. Print the results to console and results file.            
f = open(resultsFile, 'w+')
f.write('River mouth or POI, total annual change in 10^6 m^3, monthly changes in m^3/s\n')
for mouth in mouths:
    nodes=cypher.execute('MATCH p=()-[r*]->(n {name:\''+mouth+'\'}) RETURN nodes(p)')
    if mouth=='Hooghly mouth' and len(nodes)==0:
        node=cypher.execute('MATCH (n {name:\''+mouth+'\'}) RETURN n')
        total_water_change=(node[0][0].properties['water_shift'])
        monthlies=np.array([node[0][0].properties['Jan'],node[0][0].properties['Feb'],node[0][0].properties['Mar'],node[0][0].properties['Apr'],node[0][0].properties['May'],node[0][0].properties['Jun'],node[0][0].properties['Jul'],node[0][0].properties['Aug'],node[0][0].properties['Sep'],node[0][0].properties['Oct'],node[0][0].properties['Nov'],node[0][0].properties['Dec']])                
    else:
        total_water_change=0
        monthlies=np.array([0.,0,0,0,0,0,0,0,0,0,0,0])
        nodeslist=[]
        #create list of unique nodes in the path
        for node in nodes:
            nodename=pointname2varname(node[0][0].properties['name'])
            if nodename not in nodeslist:
                nodeslist.append(nodename)
                total_water_change+=(node[0][0].properties['water_shift'])
                pull_monthlies=np.array([node[0][0].properties['Jan'],node[0][0].properties['Feb'],node[0][0].properties['Mar'],node[0][0].properties['Apr'],node[0][0].properties['May'],node[0][0].properties['Jun'],node[0][0].properties['Jul'],node[0][0].properties['Aug'],node[0][0].properties['Sep'],node[0][0].properties['Oct'],node[0][0].properties['Nov'],node[0][0].properties['Dec']])                
                monthlies+=pull_monthlies
    
    DPM=30.4166666; #Days per month. Assume that all the months are the same length.               
    print mouth+': '+str(np.int(np.round(total_water_change)))+'*10^6 m^3/y, Monthly values:'+(",".join([str(np.int(np.round(x*10**6/(60*60*24*DPM)))) for x in monthlies]))    
    f.write(mouth+': '+str(np.int(np.round(total_water_change)))+'*10^6 m^3/y, Monthly values:'+(",".join([str(np.int(np.round(x*10**6/(60*60*24*DPM)))) for x in monthlies]))+'\n')
f.close()

#4. Re-build the canals, for fun and exploring!
with open(linksFile, 'rU') as csvfile:
    csvreader = csv.reader(csvfile,delimiter=';')
    next(csvreader, None)  # skip the headers
    next(csvreader, None)  # skip the headers
    for row in csvreader:
        #then, create rivers
        onoff=row[0]
        if (onoff=='ON' or args.canals=='ON') and args.canals !='OFF':
            linkname=row[1]
            if linkname != '13': #because you never broke the Hooghly transfer, it's hard-coded
                starts_at_v=pointname2varname(row[2])
                ends_at_v=pointname2varname(row[3])
                other_structure=row[10]
                if row[2] not in userlist:
                    userlist.append(row[2])
                if row[3] not in userlist:
                    userlist.append(row[3])
                if other_structure not in userlist and other_structure != '':
                    userlist.append(other_structure)
                monthly=row[9]
                monthlies=monthly.split(',')
                exec('graph.create(py2neo.rel('+starts_at_v+',\"'+linkname+'\",'+ends_at_v+',type=\"canal\",transfer='+row[4]+',TL='+row[5]+',IRR='+row[6]+',DI='+row[7]+',outfall='+row[8]+',Jan='+monthlies[0]+',Feb='+monthlies[1]+',Mar='+monthlies[2]+',Apr='+monthlies[3]+',May='+monthlies[4]+',Jun='+monthlies[5]+',Jul='+monthlies[6]+',Aug='+monthlies[7]+',Sep='+monthlies[8]+',Oct='+monthlies[9]+',Nov='+monthlies[10]+',Dec='+monthlies[10]+',DamTransfer=\''+row[11]+'\'))')

#4b. Rebuild the Hooghly River also
starts_at_v=pointname2varname('Farakka Barrage')
ends_at_v=pointname2varname('Hooghly mouth')
exec('graph.create(py2neo.rel('+starts_at_v+',\"'+'Hooghly'+'\",'+ends_at_v+',type=\"river\"))')

