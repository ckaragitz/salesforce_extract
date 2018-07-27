""" Script that will connect to the Salesforce API, query objects, transform the data,
 write the data to a CSV file, and then push the file to an SFTP server. """
import csv
import time
from datetime import datetime
import unicodecsv
import pysftp
import config
from salesforce_bulk import SalesforceBulk

# Set the sftp hostkeys
cnopts = pysftp.CnOpts()
cnopts.hostkeys = None

# Create the log file and save in a variable for later use
log = open("log.txt", "a")
# Every day the program is run, log the date/time
log.write("\n" + "|---------------------------------------|" + "\n") 
log.write("PROGRAM STARTED: "),log.write(datetime.now().ctime())
log.write("\n" + "|---------------------------------------|" + "\n")

# Set the Salesforce username, password, and token
# Establish connection to Salesforce with credentials
# Include Sandbox=True if it's a Sandbox org
sf = SalesforceBulk(username=config.salesforce["username"], password=config.salesforce["password"],
	security_token=config.salesforce["token"])

# Establish connection to sftp server with credentials
sftp = pysftp.Connection(host=config.sftp["host"], username=config.sftp["username"],
	password=config.sftp["password"], cnopts=cnopts)

def sf_extract(sf_object, query, file_name):
	""" Queries Salesforce objects and creates CSV files with that data """

	# Define the job and object, then query the data
	job = sf.create_query_job(sf_object, contentType='CSV')
	batch = sf.query(job, query)
	sf.close_job(job)

	# Waits to make sure the query has been fetched
	while not sf.is_batch_done(batch):
		time.sleep(10)

	# Decode the results
	for result in sf.get_all_results_for_query_batch(batch):
	    data = unicodecsv.DictReader(result, encoding='utf-8')

	    # Opens a CSV file
	    with open(file_name + ".csv", 'w', encoding='utf-8') as out_file:
	    	count = 0

	    	# Grabs each item (dictionary) from the data and loops through it
	    	for item in data:
	    		# Save the transformed dictionary into "item"
	    		item = data_transform(sf_object, item)
	    		# Read the keys
	    		w = csv.DictWriter(out_file, item.keys())
	    		# Only writes the header once 
	    		while count != 1:
	    			w.writeheader()
	    			count += 1

	    		# Checks if Contact is an internal flagstar user, since users are created as Contacts too
	    		if (sf_object == "Contact" or sf_object =="Account") and ("@flagstar.com" in item["Email"]):
	    			# If Email is a flagstar email, do nothing (skip the row)
	    			pass
	    		else:
	    			# Otherwise, write each row to the CSV file
	    			w.writerow(item)

	    sftp_put(file_name)

def data_transform(sf_object, item):
	""" Take the results of a query job and transform the data (append
	a "Contact Type" header and value, depending on the Salesforce object). """
	# This is required because Surefire needs to differentiate between Contacts and Leads

	# Conditional that checks the Salesforce object and appends the correct Contact Type
	if sf_object == "Lead":
		# Appends the "Contact Type" header and "Prospect" value
		item["Contact Type"] = "Prospect"

	# Conditional that checks the Salesforce object and appends the correct Contact Type
	if sf_object == "Contact" or sf_object == "Account":
		# Appends the "Contact Type" header and "Client" value
		item["Contact Type"] = "Client"

	# Return the transformed dictionary to the sf_extract function
	return item

def sftp_put(file_name):
	""" Take the CSV file after it has been created and send it to the SFTP server. """

	# Change the SFTP directory
	with sftp.cd(): # Optional: add the directory path that you want to save the files in
		# Send the file to the SFTP server
		file_name = file_name + ".csv"
		sftp.put(file_name, preserve_mtime=True)

def date_time_log(log):
	""" Log the date/time of the query or error. """

	# Write the current time to log.txt
	log.write("\n" + datetime.now().ctime() + "\n")

def execute(log, sf_object, query, file_name):
	""" Query the data with specific objects and SOQL statements. """
		
	try:  # Try the query
		sf_extract(sf_object, query, file_name)
	except Exception as e: # If the query fails, log the results, date/time, and error
		log.write("\n" + "--! FAILED to query " + sf_object + " object !--"),date_time_log(log) 
		log.write("\n" + str(e) + "\n")
	else: # If the query is successful, log the results and date/time
		log.write("\n" + "-- Successful " + sf_object + " query --"),date_time_log(log)

# Ensures that the program is run directly and not through a module
# Replace 'sf_object' with the object you want to query
# Replace 'query' with the SOQL statement you want to use for the data
# Replace file_name with the output file name you want for the CSV file
if __name__ == "__main__":

	sf_object = "Contact" # Define the object you want to query
	query = "SELECT Id,FirstName,LastName,Email FROM Contact" # Set SOQL Query
	file_name = "contact_data" # Name the output file you set
	execute(log, sf_object, query, file_name) # Call the main function
	
	sf_object = "Lead"
	query = "SELECT Id,FirstName,LastName,Email FROM Lead"
	file_name = "lead_data"
	execute(log, sf_object, query, file_name)
	
	sf_object = "Opportunity"
	query = "SELECT Id,StageName FROM Opportunity"
	file_name = "opportunity_data"
	execute(log, sf_object, query, file_name)
	
# Close the SFTP connection and log file
sftp.close()
log.close()



