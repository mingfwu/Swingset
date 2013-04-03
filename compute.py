#!/usr/bin/python

import sys, os, time, json, csv, ConfigParser
import datetime, bisect, collections, numpy

if len(sys.argv)  < 2:
        print "Usage:",sys.argv[0]," [config file]" 
        sys.exit(2);

global valueThreshold,precision
valueThreshold = 3
precision=3

def main():
        configFile = sys.argv[1]
        globalConfigFile = "globals.cfg"

        #print "GLOBAL CONFIG FILE: ", globalConfigFile
        print "CONFIG FILE: ", configFile
        #if (not validateFile(configFile) or not validateFile(globalConfigFile)):
	if not validateFile(configFile):
                sys.exit(1)

        # Set Globals
        #globals = setGlobals(globalConfigFile)

        # Load Template Config
        reportNames, reports, outputFile = loadConfigs(configFile)   
        
	data = {}
	for name in reportNames:
		file = reports[name]
		totals, records = loadBaseline(file)
		averages, mean, median = calcStats(totals, records)
		thresholdOptions = [mean, median, valueThreshold]
		filteredVals = filterVals(averages, thresholdOptions)
		data[name] = { 'values':averages, 'filtered_values':filteredVals, 'mean':mean, 'median':median }
	outputData = extractData(data)
	headers = ["name"] + reportNames
	writeData(headers,outputFile,outputData)

def validateFile(file): 
	if not os.path.isfile(file):
		print file, "could not be found"
		return False
	else:
		return True

def setGlobals(configFile):
	config = ConfigParser.ConfigParser()
	config.readfp(open(configFile))
	global global_cfg
	global_cfg = {}
	for record in config.items("globals"):
		global_cfg[record[0]] = record[1]
	
	

def loadConfigs(configFile):
	config = ConfigParser.ConfigParser()
	config.readfp(open(configFile))
	configItems = {}
	
	for record in config.items("config"):
		if record[0] == "reports": 
			configs=record[1].split(',')
		elif record[0] == "outputfile":
			outputFile = record[1]
		elif record[0] == "valuethreshold":
			global valueThreshold
			valueThreshold = int(record[1])
		elif record[0] == "precision":
			global precision
			precision = int(record[1])
		else:
			configItems[record[0]] = record[1]

	reportNames = []
	reports = {}
	for item in configs:
		nameKey = item+'_name'
		valueKey = item+'_value'
		
		reportName = configItems[nameKey]
		fileName = configItems[valueKey]
		if not validateFile(fileName):
			print "WARNING:",reportName,"file",fileName,"does not exist"

		reports[reportName] = fileName	
		reportNames.append(reportName)

	return reportNames, reports, outputFile


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
				values[setName] = round(setValues["values"][key],precision)
			else:
				values[setName] = 0
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
	print "Loading data from",file
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
		#if count % 100 == 0:
		#	print count, "records processed"
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
