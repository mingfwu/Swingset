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
	configs, reportConfigs = loadConfigs(configFile)	
	#print configs, reportConfigs
	
	# Run
	metrics = processData(dataFile,reportConfigs)
	#print metrics

	outputData(metrics,reportConfigs)

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
	for record in config.items("config"):
		if record[0] == "reports": 
			configs=record[1].split(',')

	reportConfigs = [];
	for item in configs:
		print "Loading config :",item
		reportConfig = loadReportConfig(item, config.items(item))
		reportConfigs.append(reportConfig)
	

	return configs, reportConfigs

def validateReportConfig(name, configItems):
	validConfig = True
	configParams = [ "operations", "file", "format", "type" ]
	reportConfig = {}
	for param in configParams:
		if not configItems.has_key(param):
			print "ERROR:",name,"is missing value for",param
			validConfig = False
		else:
			reportConfig[param] = configItems[param]	
	return validConfig, reportConfig

	
def loadReportConfig(name, config):
	configItems = {}
	for item in config:
		configItems[item[0]] = item[1]	

	validConfig, reportConfig = validateReportConfig(name, configItems)
	operations = []

	for operation in configItems["operations"].split(","):
		operations.append(loadOperation(name, operation,configItems))

	reportConfig["operations"] = operations

	return reportConfig

	
def validateOperationConfig(reportname, opname, configItems, params): 
	validConfig = True
	#for param in params:
	#	if not configItems.has_key(param):
	#		print "ERROR:",reportname,":",opname,"is missing value for",param
	#		validConfig = False
	return validConfig


def loadOperation(reportname,opname,config):
	opParams = ["action","target","legend","filter","values","comparator"]
	operation = {}
	operation["_config"] = reportname 
	operation["_operation"] = opname
	for param in opParams:
		paramName = opname+"_"+param
		if config.has_key(paramName):
			operation[param] = config[paramName]

	validateOperationConfig(reportname, opname, operation, opParams)
	return operation
	

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

def cleanseData(jsondata):
	if not type(jsondata) == type([]):
		jsondata = [jsondata]
	count = 0
	while count < len(jsondata):
		if type(jsondata[count]) == type({}):
			jsondata.pop(count)
		else:
			count = count + 1
	return jsondata

def retrieveData(jsondata,field):
	fieldHierarchy = field.split(".")
	for subField in fieldHierarchy:
		if type(jsondata) == type([]):
			newrecords = []
			for record in jsondata:
				if record.has_key(subField):
					newrecords.append(traverseHierarchy(record, subField))
			jsondata = newrecords	
		else:
			jsondata = traverseHierarchy(jsondata,subField)

	jsondata = cleanseData(jsondata)
	return jsondata

def extractMetric(operation, json, records, value, key=None):
	print "IN : extractMetric"
	action = operation["action"]

	# MW: This is suspect...
	if not key == None:
		legend = key
	else:
		if operation.has_key("legend"):
			legend = operation["legend"]
		else:
			legend = operation["target"]

	if action == "count":
		if records.has_key(legend):
			records[legend] = records[legend] + 1
		else:
			records[legend] = 1

	elif action == "uniquecount":
		# Check to see if this is our first uniquecount value or not
		if records.has_key(legend):
			keys = records[legend]["keys"]

			# Check to see if the value being checked for uniqueness exists or not
			if not keys.has_key(value):
				keys[value] = 1
			else:
				# We might as well append it here. 
				keys[value] = keys[value] + 1

		else:
			keys = dict()
			keys[value] = 1
		records[legend] = { global_cfg["uniquekey"] : len(keys), "keys" : keys }

	elif action == "sum":
		if records.has_key(legend):
			records[legend] = float(records[legend]) + float(value)
		else:
			records[legend] = float(value)
	elif action == "avg":
		value = float(value)
		if records.has_key(legend):
			records[legend][global_cfg["avgkey"]].append(value)
		else:
			records[legend] = { global_cfg["avgkey"] : [value] }
	return records

def extractKeys(operation, json):
	#print "IN: extractKeys"
	values = retrieveData(json,operation["target"])	
	print values
	return values

def filterData(operation, json, keys):
	#print "IN: filterData"
	action = operation["action"]
	if action == "exclude_key" or action == "exclude_data":
		# Assume we pass the data unless otherwise instructed
		proceed = True
	else:
		proceed = False
	if action == "exclude_key" or action == "include_key":
		print operation
		specifiedKeys = operation["values"].split(",")
		print specifiedKeys
		for key in specifiedKeys:
			print key
			if key in keys:
				if action == "exclude_key":
					proceed = False
				if action == "include_key":
					proceed = True
				print "FILTER:", proceed
				return proceed
	if action == "exclude_data" or action == "include_data":
		dataFilters = operation["values"].split(",")
		data = rerieveData(json, operation["target"])
		filtertype = operation["comparator"]
		# comparator can be equals, contains, gt, ge, lt, le
		for filter in dataFilters:
			for record in data:
				criteriaMet = False;
				if filtertype == "equals" and record == filter:
					criteriaMet = True
				elif filtertype == "contains" and record.find(filter) != -1:
					criteriaMet = True
				elif filtertype == "gt" and float(record) > float(filter):
					criteriaMet = True
				elif filtertype == "ge" and float(record) >= float(filter):
					criteriaMet = True
				elif filtertype == "lt" and float(record) < float(filter):
					criteriaMet = True
				elif filtertype == "le" and float(record) <= float(filter):
					criteriaMet = True
				if action == "exclude_data" and criteriaMet:
					proceed = False
				if action == "include_data" and criteriaMet:
					proceed = True
				return proceed
	return proceed
	

				 
	
	

def executeOperation(operation, json, records, keys):
	# Determine the type of operation: key identification, metric extraction, data processing

	# Key identification operations are: return
	# 	Key identification must always have a target
	# Data processing operations are: exclude_data, include_data, exclude_key, include_key
	# 	Data processing must always have a target and a set of comma separated filter operations
	# Metric extraction operations are: sum, average, mean, count, uniquecount
	# 	Metric extraction operations must always have a target


	action = operation["action"]
	proceed = True
	if action == "return":
		keys = extractKeys(operation, json)

	if action == "sum" or action == "average" or action == "mean" or action == "count" or action == "uniquecount":
		# Retrieve the data for the target:
		values = retrieveData(json,operation["target"])
		if keys == None:
			for value in values:
				records = extractMetric(operation, json, records, value)
		else:
			for key in keys:
				for value in values:
					records = extractMetric(operation, json, records, value, key)

	if action == "exclude_data" or action == "include_data" or action == "exclude_key" or action == "include_key":
		proceed = filterData(operation, json, keys)

	return proceed, keys, records


def extractReportMetrics(json, report, records):
	operations = report["operations"]
	keys = None
	for operation in operations:
		proceed, keys, records = executeOperation(operation, json, records, keys)
		if not proceed:
			print "extractReportMetric : criteria not met"
			break

	outputData = records
	return outputData

# Takes a dictionary of existing metrics and either appends the metrics with the fields 
# or creates a new dictionary record based on the json object
# Returns the metrics dictionary
def extractMetrics(json, metrics, configs):

	# Data should be stored as:
	# { outputfile : { date : { name : value } } }
	# or
	# { outputfile : { metricname : value } 

	for report in configs:
		outputfile = report["file"]
		outputtype = report["format"]
		graphtype = report["type"]
	
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

				metricdata = extractReportMetrics(json,report,metricdata)
				outputdata[interval] = metricdata;
				metrics[outputfile] = outputdata
			else:
				metricdata = outputdata;
				metricdata = extractReportMetrics(json,report,metricdata)
				metrics[outputfile] = metricdata
		except Exception, e:
			#print "Exception:",e
			continue;

	return metrics;

	
def processData(datafile,configs):
	f = open(datafile, 'r')
	
	metrics = dict() 
	count = 0
	for line in f:
		json_object = json.loads(line)

		metrics = extractMetrics(json_object, metrics, configs)

		# Store: date, name, value
		# Store: name, value
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
	for report in configs:
		print report
                outputfile = report["file"]
                outputtype = report["format"]
                graphtype = report["type"]

		# The metric type will be determined by the last operation executed
		finalOperation = report["operations"][len(report["operations"])-1]
		print finalOperation
		metrictype = finalOperation["action"]

		if graphtype == "line":
			header = ["date", "name", "value"]
		else:
			header = ["name","value"]
		
	
		if files.has_key(outputfile):
			continue;
			# Append to the existing file
			#f = open(outputfile,'ab');
		else:
			# Overwrite the existing file
			f = open(outputfile,'wb');

		outputwriter = f
		if outputtype == "csv":
			outputwriter = csv.writer(f)
		if outputtype == "tsv":
			return;
		if outputtype == "json":
			return

		# write the header if necessary:
		if not files.has_key(outputfile):
			files[outputfile] = outputfile 
			writeFormatData(header,outputwriter,outputtype)
			
		if metrics.has_key(outputfile):
			data = metrics[outputfile]

			writeData(graphtype,data,outputwriter,outputtype,metrictype);
		
		f.close()

		

main()
