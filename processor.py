#!/usr/bin/python

import sys, os, time, json, csv, ConfigParser
import datetime, bisect, collections

if len(sys.argv)  < 3:
	print "Usage:",sys.argv[0]," [config file] [data prefix]"
	sys.exit(2);

def main():
	configFile = sys.argv[1]
	dataPrefix = sys.argv[2]
	globalConfigFile = "globals.cfg"

	print "GLOBAL CONFIG FILE: ", globalConfigFile
	print "CONFIG FILE: ", configFile
	print "DATA PREFIX: ", dataPrefix 
	if (not validateFile(configFile) or not validateFile(globalConfigFile)):
		sys.exit(1)

	# Set Globals
	globals = setGlobals(globalConfigFile)

	# Load Configs
	configs, reportConfigs = loadConfigs(configFile)	
	#print configs, reportConfigs
	
	# Run
	metrics = processData(dataPrefix,reportConfigs)
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

	configError = False;
	reportConfigs = [];
	for item in configs:
		#print "Loading config :",item
		configErrorExists,reportConfig = loadReportConfig(item, config.items(item))
		if configErrorExists:
			configError = True
		reportConfigs.append(reportConfig)

	if configError:
		print "Configuration errors exist. Please review errors and correct before running again"
		sys.exit(2)

	return configs, reportConfigs

def validateReportConfig(name, configItems):
	validConfig = True
	# Removing format requirement for now
	configParams = [ "operations", "file", "type" ]
	reportConfig = {}
	for param in configParams:
		if not configItems.has_key(param):
			print 'ERROR: REPORT "', name,'" does not contain an entry for the "',param,'" field'
			sys.exit(2)
			validConfig = False
		else:
			reportConfig[param] = configItems[param]	

	if not reportConfig["type"] in ['summary','line','text']:
		validConfig = False
		print 'ERROR: Report "',name,'" : "type" field contains an invalid value. must be in: line, summary'


	return validConfig, reportConfig

	
def loadReportConfig(name, config):
	configItems = {}
	for item in config:
		configItems[item[0]] = item[1]	

	validConfig, reportConfig = validateReportConfig(name, configItems)
	operations = []

	validOperations = True
	containsSummary = False

	for operation in configItems["operations"].split(","):
		summaryOperation, validOperation,loadedOperation = loadOperation(name, operation,configItems)
		if not validOperation: 
			validOperations = False
		if summaryOperation:
			containsSummary = True
		operations.append(loadedOperation)

	reportConfig["operations"] = operations

	if not validConfig or not validOperations or not containsSummary:
		return True,reportConfig
	else: 
		# Flush the existing file if there is a file of type text which is appended to
		if reportConfig["type"] in ['text']:
			f = open(reportConfig["file"],'wb')
			f.close()

		return False,reportConfig

def validateOperationParams(reportname, opname, operation, requiredParams, optionalParams):
	validConfig = True
	for field in requiredParams:
		if not operation.has_key(field):
			validConfig = False
			print '*** ERROR: Report "',reportname,'" : Operation "',opname,'" : Field "',field,'" not found'
		if field == 'comparator':
			if not operation[field] in ['equals','contains','gt','ge','lt','le']:
				print '*** ERROR: Report "',reportname,'" : Operation "',opname,'" : "',field,'" contains invalid value. must be in: equals, contains, gt, ge, lt, le'
				validConfig = False
	for field in optionalParams:
		if not operation.has_key(field):
			#print 'INFO : Report "',reportname,'" : Operation "',opname,'" : Optional Field "',field,'" not found'
			continue
	return validConfig

	
def validateOperationConfig(reportname, opname, operation): 
	summaryOperation = False

	# Every operation requires an action and target
	if not operation.has_key("action"): 
		print "*** ERROR:",reportname,":",opname,"does not contain an action"
		sys.exit(2)

	# Allowed actions: include_data, exclude_data, include_key, exclude_key, return, return_tokens, sum, average, mean, count, uniquecount
	if operation["action"] in ['include_data','exclude_data']:
		requiredParams=['target','comparator','values']
		optionalParams=[]
		validConfig = validateOperationParams(reportname, opname, operation, requiredParams, optionalParams)

	elif operation["action"] in ['include_key','exclude_key']:
		requiredParams=['values']
		optionalParams=[]
		validConfig = validateOperationParams(reportname, opname, operation, requiredParams, optionalParams)

	elif operation["action"] in ['return']:
		requiredParams=['target']
		optionalParams=[]
		validConfig = validateOperationParams(reportname, opname, operation, requiredParams, optionalParams)

	elif operation["action"] in ['print']:
		requiredParams=['targets']
		optionalParams=[]
		validConfig = validateOperationParams(reportname, opname, operation, requiredParams, optionalParams)
		summaryOperation = True

	elif operation["action"] in ['return_tokens']:
		requiredParams=['target']
		optionalParams=['min_length','max_length']
		validConfig = validateOperationParams(reportname, opname, operation, requiredParams, optionalParams)

	elif operation["action"] in ['sum','average','count','uniquecount','mean']:
		summaryOperation = True
		requiredParams = ['target']
		optionalParams = ['legend']
		validConfig = validateOperationParams(reportname, opname, operation, requiredParams, optionalParams)

	else:
		validConfig = False
		print '** ERROR Report: "',reportname,'" : Operation "',opname,'" invalid action specified. Allowed actions are: sum, average, count, uniquecount, return, return_tokens, include_key, exclude_key, include_data, exclude_data'

	return summaryOperation,validConfig


def loadOperation(reportname,opname,config):
	opParams = ["action","target","targets","legend","filter","values","comparator","min_length","max_length"]
	operation = {}
	operation["_config"] = reportname 
	operation["_operation"] = opname
	for param in opParams:
		paramName = opname+"_"+param
		if config.has_key(paramName):
			operation[param] = config[paramName]

	isActionConfig, isValidConfig = validateOperationConfig(reportname, opname, operation)
	return isActionConfig, isValidConfig, operation
	

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

def retrieveData(jsondata,fields):
	currentdata = ''
	for field in fields.split(","):
		retrieveddata = retrieveFieldData(jsondata,field)
		# Three scenarios: Symmetrical arrays, String and array, Array and string
		# If one of these scenarios isn't matched, then we abort and just take the values that we have
		if currentdata == '':
			currentdata = retrieveddata
		elif type(retrieveddata) == type([]) and type(currentdata) == type([]):
			# Check to see if the lengths are the same. Then, append retrieveddata to currentdata
			if len(retrieveddata) == len(currentdata):
				count = 0
				while count < len(currentdata):
					if retrieveddata[count] == None:
						jsonvalue=''
					else:
						jsonvalue = str(retrieveddata[count])
					if currentdata[count] == None:
						currentvalue = ''
					else:
						currentvalue = str(currentdata[count])
					currentdata[count] = (currentvalue + ' ' + jsonvalue).strip()
					count += 1
		elif type(retrieveddata) == type([]) and type(currentdata) == type(str()):
			count = 0
			while count < len(retrieveddata):
				if retrieveddata[count] == None:
					jsonvalue=''
				else:
					jsonvalue = str(retrieveddata[count])
				retrieveddata[count] = (currentdata + ' ' + jsonvalue).strip()
				count += 1
			currentdata = retrieveddata
		elif type(retrieveddata) == type(str()) and type(currentdata) == type([]):
			count = 0
			while count < len(retrieveddata):
				if currentdata[count] == None:
					currentvalue = ''
				else:
					currentvalue = str(currentdata[count])
				currentdata[count] = (currentvalue + ' ' + retrieveddata).strip()
				count += 1
		else:
			currentdata = retrieveddata
	return currentdata
		

def retrieveFieldData(jsondata,field):
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
	#print "IN : extractMetric"
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
	elif action == "average":
		value = float(value)
		if records.has_key(legend):
			records[legend][global_cfg["avgkey"]].append(value)
		else:
			records[legend] = { global_cfg["avgkey"] : [value] }
	return records

def extractTokens(operation, values):
	if operation.has_key("min_length"):
		minLength = float(operation["min_length"])
	else:
		minLength = 4
	if operation.has_key("max_length"):
		maxLength = float(operation["max_length"])
	else:
		maxLength = 100

	tokens = [];
	for value in values:
		# Need to replace commas for CSV formatting
		valuetokens = value.replace(',',' ').split(' ')
		for token in valuetokens:
			if len(token) >= minLength and len(token) <= maxLength:
				tokens.append(token.upper())
		
	return tokens

def extractKeys(operation, json):
	#print "IN: extractKeys"
	values = retrieveData(json,operation["target"])	
	if operation["action"] == "return_tokens":
		values = extractTokens(operation, values)
	return values

def filterData(operation, json, keys):
	#print "IN: filterData"
	action = operation["action"]
	if action == "include_data":
		# Only pass the data if we match the filter
		proceed = False
	else:
		proceed = True
	if action == "exclude_key" or action == "include_key":
		specifiedKeys = operation["values"].split(",")
		returnedKeys = []
		for key in specifiedKeys:
			if action == "include_key" and key in keys:
				# This is a desired key. include it
				returnedKeys.append(key)
			elif action == "exclude_key" and key in keys:
				keys.pop(key)
		if action == "exclude_key":
			returnedKeys = keys
		if len(returnedKeys) == 0:
			proceed = False;
		return proceed, returnedKeys
	if action == "exclude_data" or action == "include_data":
		dataFilters = operation["values"].split(",")
		data = retrieveData(json, operation["target"])
		filtertype = operation["comparator"]
		# comparator can be equals, contains, gt, ge, lt, le
		for filter in dataFilters:
			for record in data:
				criteriaMet = False;
				if filtertype == "equals":
					if type(record) == type(str()):
						if record.upper() == filter.upper():
							criteriaMet = True
							break
					else:
						if record == filter:
							criteriaMet = True
							break
				elif filtertype == "contains" and record.upper().find(filter.upper()) != -1:
					criteriaMet = True
					break
				elif filtertype == "gt" and float(record) > float(filter):
					criteriaMet = True
					break
				elif filtertype == "ge" and float(record) >= float(filter):
					criteriaMet = True
					break
				elif filtertype == "lt" and float(record) < float(filter):
					criteriaMet = True
					break
				elif filtertype == "le" and float(record) <= float(filter):
					criteriaMet = True
			if criteriaMet:
				break
		if action == "exclude_data" and criteriaMet:
			proceed = False
		if action == "include_data" and criteriaMet:
			proceed = True
	return proceed,keys
	

				 
	
	

def executeOperation(operation, json, records, keys, report):
	# Determine the type of operation: key identification, metric extraction, data processing

	# Key identification operations are: return
	# 	Key identification must always have a target
	# Data processing operations are: exclude_data, include_data, exclude_key, include_key
	# 	Data processing must always have a target and a set of comma separated filter operations
	# Metric extraction operations are: sum, average, mean, count, uniquecount
	# 	Metric extraction operations must always have a target


	action = operation["action"]
	proceed = True

	if action == "print":
		records = performPrint(operation,json, report) 

	if action == "return" or action == "return_tokens":
		keys = extractKeys(operation, json)

	elif action == "sum" or action == "average" or action == "mean" or action == "count" or action == "uniquecount":
		# Retrieve the data for the target:
		values = retrieveData(json,operation["target"])
		if keys == None:
			for value in values:
				records = extractMetric(operation, json, records, value)
		else:
			for key in keys:
				for value in values:
					records = extractMetric(operation, json, records, value, key)

	elif action == "exclude_data" or action == "include_data" or action == "exclude_key" or action == "include_key":
		proceed, keys = filterData(operation, json, keys)

	return proceed, keys, records


def extractReportMetrics(json, report, records):
	operations = report["operations"]
	keys = None
	for operation in operations:
		proceed, keys, records = executeOperation(operation, json, records, keys, report)
		if not proceed:
			#print "extractReportMetric : criteria not met"
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
		#outputtype = report["format"]
		outputtype = 'csv'
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

def performPrint(operation,json,report):
	f = open(report["file"],'ab')
	lines=[]
	for target in operation["targets"].split(','):
		target = target.strip()
		try: 
			targetData = retrieveData(json,target)	
			if type(targetData) == type(str()):
				lines.append(target.upper()+':\t\t' + targetData+'\n')
			else:
				for record in targetData:
					lines.append(target.upper()+':\t\t' + record+'\n')
		except Exception, e:
			continue
	if len(lines) > 0:
		lines.append("\n")
		f.writelines(lines)
	f.close()


def getTargets(prefix):
	fileDir = os.path.dirname(prefix)
	prefixname = os.path.basename(prefix)
	targets = []
	for file in os.listdir(fileDir):
		if file.find(prefixname) == 0:
			targets.append(fileDir+'/'+file)

	return targets
	
def processData(dataPrefix,configs):
	targets = getTargets(dataPrefix)
	count = 0
	metrics = dict() 

	for target in targets:
		#print "Processing",target
		f = open(target, 'r')
		
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
					#print "Error occurred writing for",graphType,type, metric, datestring, k, v
					continue;
	else:
		# Inserting code here to manipulate and normalize case
		new_data = {}

		for k, v in data.iteritems():
			if new_data.has_key(k.upper()):
				#print "Merging data for",k,v,new_data[k.upper()][1]
				key = new_data[k.upper()][0]
				if not isinstance(v, dict):
					value = new_data[k.upper()][1] + v
				else:
					# The value is either a uniquekey or averagekey
					dictvalue = new_data[k.upper()][1]
					if dictvalue.has_key(global_cfg["uniquekey"]):
						keys = dict(dictvalue["keys"].items() + v["keys"].items())
						#uniquekeys = dictvalue[global_cfg["uniquekey"]] + v[global_cfg["uniquekey"]]
						uniquekeys = len(keys)
						value = { global_cfg["uniquekey"]: uniquekeys, "keys":keys }
					elif dictvalue.has_key(global_cfg["avgkey"]):
						values = dictvalue[global_cfg["avgkey"]]
						value = { global_cfg["avgkey"]: [values] }
			
				new_data[k.upper()] = [key, value]
			else:
				new_data[k.upper()] = [k,v]
				
		for data in new_data.values():
			k = data[0]
			v = data[1]
			try: 
				record = [k,getValues(metric, v)]
				writeFormatData(record,outputWriter,type)
			except:
				#print "Error occurred writing for ",graphType, type, metric, k, v
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
		outputfile = report["file"]
        	#outputtype = report["format"]
		outputtype = 'csv'
        	graphtype = report["type"]

        	if graphtype == "text":
	        	# The file should have already been genearted
        		continue

		# The metric type will be determined by the last operation executed
		finalOperation = report["operations"][len(report["operations"])-1]
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
