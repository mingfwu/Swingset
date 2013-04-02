#!/usr/bin/python

import sys, os, time, json, csv, ConfigParser
import datetime, bisect, collections, numpy

if len(sys.argv)  < 2:
        print "Usage:",sys.argv[0]," [config file]" 
        sys.exit(2);

def old_main():
        configFile = sys.argv[1]
        globalConfigFile = "globals.cfg"

        print "GLOBAL CONFIG FILE: ", globalConfigFile
        print "CONFIG FILE: ", configFile
        if (not validateFile(configFile) or not validateFile(globalConfigFile)):
                sys.exit(1)

        # Set Globals
        globals = setGlobals(globalConfigFile)

        # Load Template Config
        templateDefaults, layout, graphs, outputfile = loadLayout(configFile)   
        
        # Render graphs
        renderGraphs(graphs, templateDefaults)

        # Render layout
        renderHTML(layout, graphs, templateDefaults, outputfile)

def main():
	reports = { 'gen_pop_baseline':'gp_entities.csv', 'wi_baseline':'wi_entities.csv'}
	targetFile = "test.csv"
	data = {}
	dir = sys.argv[1]
	for name,file in reports.iteritems():
		file = dir +'/'+file
		totals, records = loadBaseline(file)
		averages, mean, median = calcStats(totals, records)
		thresholdOptions = [mean, median, 2]
		filteredVals = filterVals(averages, thresholdOptions)
		data[name] = { 'values':averages, 'filtered_values':filteredVals, 'mean':mean, 'median':median }
	outputData = extractData(data)
	headers = ["name"] + reports.keys()
	writeData(headers,targetFile,outputData)

def writeData(headers, file,output):
	f = open(file, 'wb')
	writer = csv.writer(f)
	writer.writerow(headers)
	for k, v in output.iteritems():
		record = []
		for header in headers:
			record.append(v[header])
		writer.writerow(record)
	f.close()
	
	
		

def extractData(data):
	output = {}
	keys = extractKeys(data)
	for key in keys:
		values = {"name":key}
		for setName, setValues in data.iteritems():
			if setValues["values"].has_key(key):
				values[setName] = setValues["values"][key]
			else:
				values[setName] = ''
		output[key] = values	
	return output
		

def extractKeys(data):
	# Assemble the master list of all unique values that need to be compiled
	keys = []
	for set in data.keys():
		dataSet = data[set]["filtered_values"]
		for key in dataSet.keys():
			if key not in keys:
				keys.append(key)
	return keys
	

def loadBaseline(file):
	baselineTotal = {}
	baselineRecords = {}
	headers=['date','name','value']
 	f = open(file,'rb') 
	reader = csv.DictReader(f)
	count = 0
	for row in reader:
		if baselineTotal.has_key(row["name"]):
			baselineTotal[row["name"]] = baselineTotal[row["name"]] + float(row["value"])
			baselineRecords[row["name"]] = baselineRecords[row["name"]] + 1
		else:
			baselineTotal[row["name"]] = float(row["value"])
			baselineRecords[row["name"]] = 1
		count += 1
		if count % 100 == 0:
			print count, "records processed"
	f.close()
	return baselineTotal, baselineRecords

def calcStats(totals,records):
	averages = {}
	for key in totals:
		averages[key] = totals[key] / records[key]
	mean = numpy.mean(averages.values())
	median = numpy.median(averages.values())
		
	return averages, mean, median

def filterVals(values, thresholds):
	threshold = numpy.amax(thresholds)
	output = {}
	for k,v in values.iteritems():
		if v >= threshold:
			output[k] = v

	return collections.OrderedDict(sorted(output.items(), key = lambda x: x[1], reverse=True))


main()
