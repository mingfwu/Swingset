#!/usr/bin/python

import sys, os, time, json, csv, ConfigParser
import datetime, bisect, collections

if len(sys.argv)  < 3:
	print "Usage:",sys.argv[0]," [config file] [data file]"
	sys.exit(2);

def main():
	configFile = sys.argv[1]
	dataFile = sys.argv[2]
	globalConfigFile = "globals.cfg"

	print "GLOBAL CONFIG FILE: ", globalConfigFile
	print "CONFIG FILE: ", configFile
	print "DATA FILE: ", dataFile
	if (not validateFile(configFile) or not validateFile(dataFile) or not validateFile(globalConfigFile)):
		sys.exit(1)

	# Set Globals
	globals = setGlobals(globalConfigFile)

	# Load Configs
	configs = loadConfigs(configFile)	
	
	# Run
	metrics = processData(dataFile,configs)
	outputData(metrics,configs)

def setGlobals(configFile):
	config = ConfigParser.ConfigParser()
	config.readfp(open(configFile))
	global global_cfg
	global_cfg = {}
	for record in config.items("globals"):
		global_cfg[record[0]] = record[1]
	
	

def loadConfigs(configFile):
	f = open(configFile, 'r')
	configs = []
	for line in f:
		# Ignore comments and empty lines
		if not line.strip().find("#") == 0 and len(line.strip()) > 0:
			configs.append(line)
			print "LOADED CONFIG:",line

	f.close()
	return configs

def validateFile(file): 
	if not os.path.isfile(file):
		print file, "could not be found"
		return False
	else:
		return True

# Returns the finish time and date of the interval period based on a 24 hour clock
def calculateInterval(date,intervalVal, format):
	
	#http://docs.python.org/2/library/time.html
	#Mon, 26 Nov 2012 08:00:03 +0000
	#%a, %d %b %Y %H:%M:%S +0000

	sourceTime = time.strptime(date, format)
	sourceDateTime = datetime.datetime.fromtimestamp(time.mktime(sourceTime))
	#print date,sourceDateTime

	interval = datetime.timedelta(seconds=intervalVal)
	start = datetime.datetime(sourceDateTime.year, sourceDateTime.month, sourceDateTime.day, 0, 0, 0)
	grid = [start + n*interval for n in range(int(86400/intervalVal)+1)]
	bins = collections.defaultdict(list)
	idx = bisect.bisect(grid,sourceDateTime)
	return grid[idx]
	
def traverseHierarchy(data,fieldName):
	return data[fieldName]

def retrieveData(jsondata,field):
	fieldHierarchy = field.split(".")
	for subField in fieldHierarchy:
		if not subField == None:
			jsondata = traverseHierarchy(jsondata,subField)
	return jsondata

def processField(field):
	fieldName = field.split("|")[0].strip()
	if len(field.split("|")) > 1:
		prettyName = field.split("|")[1].strip()
	else:
		prettyName = fieldName.strip()
	return fieldName, prettyName 

def processAction(action,records,key,prettyName,value=None):
	#if action == "avg" or action == "sum":
	#	print action, key, value
	if action == "count":
		if records.has_key(key):
			records[key] = records[key] + 1
		else:
			records[key] = 1
	elif action == "sum":
		if records.has_key(key):
			records[key] = float(records[key]) + float(value)
		else:
			records[key] = float(value)
	elif action == "totalcount":
		if records.has_key(prettyName):
			records[prettyName] = records[prettyName] + 1
		else:
			records[prettyName] = 1
	elif action == "uniquecount":
		if records.has_key(prettyName):
			keys = records[prettyName]["keys"]
			if not keys.has_key(key):
				keys[key] = 1
		else:
			keys = dict()
			keys[key] = 1
		records[prettyName] = { global_cfg["uniquekey"] : len(keys), "keys" : keys }
	elif action == "avg":
		if value == None:
			value = float(key)
		else: 
			value = float(value)
		if records.has_key(key):
			records[key][global_cfg["avgkey"]].append(value)
		else:
			records[key] = { global_cfg["avgkey"] : [value] }

	return records

def extractMetricsFromField(json,fields,currentValues,action="count"):
	# field: fieldname|prettyname:subvalue|prettyname,subvalue|prettyname:fieldname2
	# split on :, field 0
	# insert logic here to process the field and values
	# if field contains values... 
	primaryFieldName, primaryPrettyFieldName = processField(fields[0])
	#print primaryFieldName, primaryPrettyFieldName
	if len(fields) > 1:
		subFields = fields[1].split(",")
		subFieldList = dict()
		for record in subFields:
			subField = processField(record)
			subFieldList[subField[0]] = subField[1]
			
	else: 
		subFields = []
	if len(fields) >= 3:
		secondaryFieldName,secondaryPrettyFieldName= processField(fields[2])
	else: 
		secondaryFieldName = ""
		secondaryPrettyFieldName = ""

	data = retrieveData(json,primaryFieldName)
	if not type(data) == type([]):
		data = [data]
	
	if len(subFields) > 0:
		# We have tags or explicit values we want to match
		for datarecord in data:
			if subFieldList.has_key(datarecord) or subFieldList.has_key("*"): 
				# Expected match was found
				# Do we need to perform another data fetch:
				if ((action == "sum" or action == "count" or action == "avg") and not secondaryFieldName == ""):
					# Retrieve the data from the other field
					data2 = retrieveData(json, secondaryFieldName)
					
					#print "Processing secondary target for ",action,primaryFieldName, datarecord, secondaryFieldName
					currentValues = processAction(action,currentValues,datarecord,secondaryPrettyFieldName,data2)
				elif (action == "uniquecount" or action == "totalcount"):
					data2 = retrieveData(json, secondaryFieldName)
					currentValues = processAction(action,currentValues,data2,datarecord)
				else:
					currentValues = processAction(action,currentValues,datarecord,secondaryPrettyFieldName)
	else:
		for datarecord in data:
			currentValues = processAction(action,currentValues,datarecord,primaryPrettyFieldName) 
			
	return currentValues;


# Takes a dictionary of existing metrics and either appends the metrics with the fields 
# or creates a new dictionary record based on the json object
# Returns the metrics dictionary
def extractMetrics(json, metrics, configs):
	# outputfile:graphtype:metrictype:fieldname|prettyname:subvalue|prettyname:fieldname2
	#   fieldname2 should only exist for the countunique, countwhere and sumwhere clauses where a set of subvalues exist
	#   if using subvalues without fieldname2, only counts should be used
	# graphtype: line or summary
	# metrictype: count, uniquecount, totalcount, sum, countwhere, sumwhere
	# line:uniquecount:interaction.author.username
	# line:count:interaction.tags:mytag1,mytag2

	# Data should be stored as:
	# { outputfile : { date : { name : value } } }
	# or
	# { outputfile : { metricname : value } 

	for config in configs:
		#print config
		config = config.split(":")
		outputfile = config[0]
		outputtype = config[1]
		graphtype = config[2]
		metrictype = config[3]
		fields = config[4:]

		# Retrieve the dataset
		if metrics.has_key(outputfile):
			outputdata = metrics[outputfile]
		else:
			outputdata = dict();

		try:
			if graphtype == "line": 
				interval = calculateInterval(json["interaction"]["created_at"], int(global_cfg["time_interval"]), global_cfg["ds_datetime_format"])
				if outputdata.has_key(interval):
					metricdata = outputdata[interval]
				else:
					metricdata = dict() 
				metricdata = extractMetricsFromField(json, fields, metricdata, metrictype);	
				outputdata[interval] = metricdata;
				metrics[outputfile] = outputdata
			else:
				metricdata = outputdata;
				metricdata = extractMetricsFromField(json, fields, metricdata, metrictype);	
				metrics[outputfile] = metricdata
		except:
			#print "Error processing",json
			continue;

	return metrics;

	
def processData(datafile,configs):
	f = open(datafile, 'r')
	
	metrics = dict() 
	count = 0
	for line in f:
		try: 
			json_object = json.loads(line)
			# Set conditional for time series axes
			field="interaction.author.username"
			field="interaction.tags"
			#extractMetricsFromField(json_object,field)
			metrics = extractMetrics(json_object, metrics, configs)
			# Store: date, name, value
			# Store: name, value
		except:
			print "ERROR reading line",count
		count = count + 1
		if count % 1000 == 0:
			print count,"lines processed"

	f.close()
	return metrics

def getValues(metric, values):
	if type(values) == type({}):
		if values.has_key(global_cfg["uniquekey"]):
			return values[global_cfg["uniquekey"]]
		if values.has_key(global_cfg["avgkey"]):
			avgvalues = values[global_cfg["avgkey"]]
			return sum(avgvalues)/len(avgvalues);
	return values;


# Need to add support for field1,field2,value (link, link title, value)
def writeData(graphType,data,outputWriter,type,metric):
	if graphType == "line":
		for date in sorted(data.iterkeys()):
			records = data[date]
			datestring = date.strftime("%Y/%m/%d %H:%M")	
			for k,v in records.iteritems():
				try: 
					record = [datestring, k, getValues(metric, v)]
					writeFormatData(record,outputWriter,type)
				except:
					print "Error occurred writing for",graphType,type, metric, datestring, k, v
					continue;
	else:
		for k,v in data.iteritems():
			try: 
				record = [k,getValues(metric, v)]
				writeFormatData(record,outputWriter,type)
			except:
				print "Error occurred writing for ",graphType, type, metric, k, v
				continue;

	
def writeFormatData(record,writer,type,headers=[]):
	if type == "csv":
		writer.writerow(record)
	if type == "tsv":
		tsvWriter(record,writer)
	if type == "json" and len(headers) > 0:
		jsonWriter(headers,record,writer)


def outputData(metrics,configs):
	files = dict()
	#print metrics
	for config in configs:
		config = config.split(":")
		outputFile = config[0]
		outputType = config[1]
		graphType = config[2]
		metricType = config[3]

		if graphType == "line":
			header = ["date", "name", "value"]
		else:
			header = ["name","value"]
		
	
		if files.has_key(outputFile):
			continue;
			# Append to the existing file
			#f = open(outputFile,'ab');
		else:
			# Overwrite the existing file
			f = open(outputFile,'wb');

		outputWriter = f
		if outputType == "csv":
			outputWriter = csv.writer(f)
		if outputType == "tsv":
			return;
		if outputType == "json":
			return

		# write the header if necessary:
		if not files.has_key(outputFile):
			files[outputFile] = outputFile
			writeFormatData(header,outputWriter,outputType)
			
		if metrics.has_key(outputFile):
			data = metrics[outputFile]

			writeData(graphType,data,outputWriter,outputType,metricType);
		
		f.close()

		

main()
