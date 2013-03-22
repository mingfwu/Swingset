#!/usr/bin/python

import sys, os, time, json, csv, ConfigParser
import datetime, bisect, collections

if len(sys.argv)  < 2:
	print "Usage:",sys.argv[0]," [config file]" 
	sys.exit(2);

def main():
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

def setGlobals(configFile):
	config = ConfigParser.ConfigParser()
	config.readfp(open(configFile))
	global global_cfg
	global_cfg = {}
	for record in config.items("globals"):
		global_cfg[record[0]] = record[1]

	template_placeholders = {}
	for record in config.items("template"):
		template_placeholders[record[0]] = record[1]
	global_cfg["template_placeholders"] = template_placeholders

	defaults = {}
	templates = {}

	if config.has_section("template_defaults"):
		for defaultrecord in config.items("template_defaults"):
			defaults[defaultrecord[0]] = defaultrecord[1]

	if config.has_section("templates"):
		for templaterecord in config.items("templates"):
			templates[templaterecord[0]] = templaterecord[1]

	defaults["templates"] = templates
	global_cfg["defaults"] = defaults


def loadGraph(configFile,graphName):
	graph = {}
	for config in configFile.items(graphName):
		graph[config[0]] = config[1]
	return graph
	
def loadLayout(configFile):
	config = ConfigParser.ConfigParser()
	config.readfp(open(configFile))
	defaults = global_cfg["defaults"]
	templates = defaults["templates"]
	layout = []
	graphs = {}


	# Legacy in case the templates still contain the globals
	if config.has_section("template_defaults"):
		for defaultrecord in config.items("template_defaults"):
			defaults[defaultrecord[0]] = defaultrecord[1]

	if config.has_section("templates"):
		for templaterecord in config.items("templates"):
			templates[templaterecord[0]] = templaterecord[1]
		defaults["templates"] = templates
		

	for layoutrecord in config.items("layout"):
		if layoutrecord[0] == "outputfile":
			outputfile = layoutrecord[1]
		if layoutrecord[0] == "rows":
			rownames = layoutrecord[1].split(",")
			for rowname in rownames:
				row = []
				for rowrecord in config.items(rowname):
					if rowrecord[0] == "graphs":
						graphnames = rowrecord[1].split(",")
					for graph in graphnames:
						graphs[graph] = loadGraph(config,graph)
						row.append(graph)
				layout.append(row)

	if outputfile == "":
		outputfile = defaults["outputfile"]
	return defaults,layout,graphs,outputfile
	

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

def getValue(key, config, defaults):
	if config.has_key(key):
		value = config[key]
	else:
		value = defaults[key]
	return value

def mapValues(graphInfo):
	map = {}
	map[global_cfg["template_placeholders"]["placeholder_dateformat"]] = global_cfg["csv_datetime_format"]
	map[global_cfg["template_placeholders"]["placeholder_width"]] = graphInfo["width"]
	map[global_cfg["template_placeholders"]["placeholder_height"]] = graphInfo["height"]
	map[global_cfg["template_placeholders"]["placeholder_scale"]] = graphInfo["scale"]
	map[global_cfg["template_placeholders"]["placeholder_datafile"]] = graphInfo["datafile"]
	map[global_cfg["template_placeholders"]["placeholder_enable_sort"]] = graphInfo["enable_sort"]
	map[global_cfg["template_placeholders"]["placeholder_enable_truncate"]] = graphInfo["enable_truncate"]
	map[global_cfg["template_placeholders"]["placeholder_maxresults"]] = graphInfo["maxresults"]
	map[global_cfg["template_placeholders"]["placeholder_sorttype"]] = graphInfo["sorttype"]
	map[global_cfg["template_placeholders"]["placeholder_header"]] = graphInfo["header"]
	map[global_cfg["template_placeholders"]["placeholder_legend_width"]] = graphInfo["legend_width"]
	map[global_cfg["template_placeholders"]["placeholder_max_textsize"]] = graphInfo["max_textsize"]
	map[global_cfg["template_placeholders"]["placeholder_min_textsize"]] = graphInfo["min_textsize"]
	return map

def getGraphInfo(graph, defaults):
	
	graphInfo = {}

	configItems = ["width","height","scale","htmlfile","graphtype","datatype","datafile","enable_sort","enable_truncate","maxresults","sorttype","header","legend_width","max_textsize","min_textsize"]

	for item in configItems:
		graphInfo[item] = getValue(item,graph,defaults)

	return graphInfo
	

def renderGraph(graph, defaults):
	graphInfo = getGraphInfo(graph, defaults)

	templateName = graphInfo["graphtype"]+'_'+graphInfo["datatype"]
	template = defaults["templates"][templateName]

	map = mapValues(graphInfo)

	if validateFile(template):
		print "Rendering",graphInfo["htmlfile"]
		src = open(template, 'r')
		target = open(graphInfo["htmlfile"], 'w')
		for line in src:
			for k,v in map.iteritems():
				line = line.replace(k,v)
			target.write(line)
		src.close()
		target.close()
			


def renderGraphs(graphs,defaults):
	for name, graph in graphs.iteritems():
		renderGraph(graph, defaults)
		

def renderRow(f,row,graphs,defaults):
	f.write("<div style=\"white-space:nowrap\">\n")
	for graph in row:
		graphData = graphs[graph]
		graphInfo = getGraphInfo(graphData, defaults)
		f.write('<iframe id="'+graph+'" src="'+graphInfo["htmlfile"]+'" height="'+graphInfo["height"]+'" width="'+graphInfo["width"]+'" frameborder="0" scrolling="no"></iframe>\n')
	f.write("</div>\n")
	

def renderHTML(layout, graphs, defaults, outputfile):
	target = outputfile;
	f = open(target, 'w')
	f.write("<html> \n")
	f.write("<head/> \n")
	f.write("<body> \n")
	for row in layout:
		renderRow(f,row, graphs, defaults)
	f.write("</body> \n")
	f.write("</html> \n")
main()
