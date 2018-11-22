""" Script that will connect to the Salesforce API, query objects, transform the data,
 write the data to a CSV file, and then push the file to an SFTP server. """

import os
import sys
import csv
from collections import OrderedDict
import time
from datetime import datetime
import config
import unicodecsv
import pysftp
import requests
from salesforce_bulk import SalesforceBulk
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QInputDialog, QLabel, QMessageBox
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import pyqtSlot
from functools import partial

class GUI(QWidget):
	""" Class that defines the GUI with a picklist and buttons """

	def __init__(self):
		super().__init__()
		self.title = 'Surefire Data Loader'
		self.left = 10
		self.top = 10
		self.width = 640
		self.height = 480
		self.Choice()
 
	def Choice(self):
		self.setWindowTitle(self.title)
		#self.setWindowIcon(QIcon('fsb_icon.png'))
		self.setGeometry(self.left, self.top, self.width, self.height)
		self.getChoice()
		self.show()

	def Buttons(self, query_date):
		self.setWindowTitle(self.title)
		#self.setWindowIcon(QIcon('fsb_icon.png'))
		self.setFixedSize(300, 300)
 
		all_label = QLabel('-Query all of the data-', self)
		all_label.move(85, 50)
		button_all = QPushButton('Query All', self)
		button_all.setToolTip('This button queries all of the objects')
		button_all.move(100, 70)
		button_all.clicked.connect(partial(self.button_all_click, query_date))

		specific_label = QLabel('-Query a specific object-', self)
		specific_label.move(77, 110)
		button_lead = QPushButton('Get Lead Contact Data', self)
		button_lead.setToolTip('This button queries the Lead object')
		button_lead.move(58, 130) 
		button_lead.clicked.connect(partial(self.button_lead_click, query_date))

		button_contact = QPushButton('Get Realtor Data', self)
		button_contact.setToolTip('This button queries the Contact object (realtors)')
		button_contact.move(75, 160) 
		button_contact.clicked.connect(partial(self.button_contact_click, query_date))

		button_loan = QPushButton('Get Customer and Loan Data', self)
		button_loan.setToolTip('This button queries the Opportunity and Financial Product objects')
		button_loan.move(37, 190) 
		button_loan.clicked.connect(partial(self.button_loan_click, query_date))
 
		self.show()
 
	def getChoice(self):
		items = ("Daily (Deltas)","Last 24 Hours","Last 48 Hours","Last 72 Hours","Initial (All Historical)")
		item, okPressed = QInputDialog.getItem(self, "Query Timeframe Options","Time Filter:", items, 0, False)
		if okPressed and item:
			timeframe = item

		with open("run_time.txt") as run_time_file:
			time_list = run_time_file.readlines()
			last_run_time = time_list[-1]

		query_date = filter_timeframe(timeframe, last_run_time)

		self.Buttons(query_date)

	@pyqtSlot()
	def button_all_click(self, query_date):
		print("Running program... Querying all...")
		query_financial_product_MO(query_date)
		query_account(query_date)
		query_lead(query_date)
		query_contact(query_date)
		sftp_put()
		post_file_to_surefire()
		record_count = get_record_count()
		QMessageBox.about(self, "Program Status", str(record_count) + " record(s) returned\n -- LOAD COMPLETE --")
		print("\n-- LOAD COMPLETE --\n")
		os.remove('reader.csv')
		os.remove(file_name)

	@pyqtSlot()
	def button_lead_click(self, query_date):
	   print("Running program... Querying Leads...")
	   query_lead(query_date)
	   sftp_put()
	   post_file_to_surefire()
	   record_count = get_record_count()
	   QMessageBox.about(self, "Program Status", str(record_count) + " record(s) returned\n -- LOAD COMPLETE --")
	   print("\n-- LOAD COMPLETE --\n")
	   os.remove('reader.csv')
	   os.remove(file_name)

	@pyqtSlot()
	def button_contact_click(self, query_date):
	   print("Running program... Querying Realtors...")
	   query_contact(query_date)
	   sftp_put()
	   post_file_to_surefire()
	   record_count = get_record_count()
	   QMessageBox.about(self, "Program Status", str(record_count) + " record(s) returned\n -- LOAD COMPLETE --")
	   print("\n-- LOAD COMPLETE --\n")
	   os.remove('reader.csv')
	   os.remove(file_name)

	@pyqtSlot()
	def button_loan_click(self, query_date):
	   print("Running program... Querying Customers and Loans... ")
	   query_financial_product_MO(query_date)
	   query_account(query_date)
	   sftp_put()
	   post_file_to_surefire()
	   record_count = get_record_count()
	   QMessageBox.about(self, "Program Status", str(record_count) + " record(s) returned\n -- LOAD COMPLETE --")
	   print("\n-- LOAD COMPLETE --\n")
	   os.remove('reader.csv')
	   os.remove(file_name)

# --------------------------------------------------------------------------- #	

def filter_timeframe(timeframe, last_run_time):
	#Gives a user the ability to select the timeframe of the query 

	if timeframe.lower() == "initial (all historical)":
		query_date = "CreatedDate <= TODAY"
	elif timeframe.lower() == "daily (deltas)":
		query_date = "LastModifiedDate >= " + str(last_run_time)
	elif timeframe.lower() == "last 24 hours":
		query_date = "LastModifiedDate >= YESTERDAY"
	elif timeframe.lower() == "last 48 hours":
		query_date = "LastModifiedDate >= LAST_N_DAYS:2"
	elif timeframe.lower() == "last 72 hours":
		query_date = "LastModifiedDate >= LAST_N_DAYS:3"
	else:
		query_date = "LastModifiedDate >= " + str(last_run_time) 

	return str(query_date)

def sf_extract(sf_object, query):
	""" Queries Salesforce objects and returns the data in an OrderedDict """

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

		return data

def csv_writer(sf_object, data):
	""" Creates a 'Reader' file, transforms the data, then writes the transformed data to an output file """

	file_name = "contact_product_data " + str(year_month_day) + ".csv"

	# Opens a CSV file
	with open("reader.csv", 'a+', encoding='utf-8', newline='') as in_file:

	   	# Grabs each item (record dictionary) from the data and loops through it
		for item in data:
			# Logic to get rid of records that are not owned by Loan Officer's
			if item["Owner.Id"] in users_list:
				item = data_transform(sf_object, item)
				writer = csv.DictWriter(in_file, item.keys())
				writer.writerow(item)

	print("Reader file built")

	with open("reader.csv", 'r+', encoding='utf-8', newline='') as in_file, open(file_name, 'w+', encoding='utf-8', newline='') as out_file:
		reader = csv.reader(in_file, delimiter=',')
		writer = csv.writer(out_file)
		writer.writerow(config.csv_header)

		for row in reader:
			try:
				status = row[28]
				date = row[29]
				if str(status) in config.milestone_keys:
					row[config.milestone_index[status]] = str(date)
			except:
				writer.writerow(row)
			else:
				writer.writerow(row)

	print(sf_object + " data appended to Output file")

def data_transform(sf_object, item):
	""" Take the results of a query job and transform the data (append
	a "Contact Type" header and value, depending on the Salesforce object). """

	item = OrderedDict(item)

	if sf_object == "Bank_Account__c":
		item["Mortgage_Status_Date__c"] = (item["Mortgage_Status_Date__c"])[:-14]
		item.update({'Contact Type':'Client'})
		item.move_to_end('Contact Type', last=False)
		item.update({'Lead Source':''})
		item.move_to_end('Lead Source', last=False)
		item.update({'App Received':''})
		item.update({'Submitted to Underwriting':''})
		item.update({'Initial/Conditional Approval':''})
		item.update({'Clear to Close':''})
		item.update({'Funded':''})
		item.update({'Denied':''})
		item.update({'Withdrawn':''})
		del item["Owner.Id"]
		if item["Opportunity__r.LeadID__c"]:
			item["Primary_Customer__r.Id"] = item["Opportunity__r.LeadID__c"]
		del item["Opportunity__r.LeadID__c"]
	if sf_object == "Lead":
		item.update({'Contact Type':'Lead'})
		item.move_to_end('Contact Type', last=False)
		item.update({'Lead Source':item["LeadSource"]})
		item.move_to_end('Lead Source', last=False)
		del item["LeadSource"]
		del item["Owner.Id"]
	if sf_object == "Opportunity":
		item.update({'Contact Type':'Lead'})
		item.move_to_end('Contact Type', last=False)
		item.update({'Lead Source':item["LeadSource"]})
		item.move_to_end('Lead Source', last=False)
		del item["LeadSource"]
		del item["Owner.Id"]
		if item["LeadID__c"]:
			item["Account.Id"] = item["LeadID__c"]
		del item["LeadID__c"]
	if sf_object == "Contact":
		item.update({'Contact Type':'Referral Source'})
		item.move_to_end('Contact Type', last=False)
		item.update({'Lead Source':''})
		item.move_to_end('Lead Source', last=False)
		del item["Owner.Id"]
		
	return item

def sftp_put():
	""" Take the CSV file after it has been created and send it to the SFTP server. """

	print("\n" + "Sending file to Flagstar SFTP server...")
	file_name = "contact_product_data " + str(year_month_day) + ".csv"
	# Change the SFTP directory (can change this to wherever the data will be stored)
	with sftp.cd("inbox"):
		sftp.put(file_name, preserve_mtime=True)

def post_file_to_surefire():
   print("Sending file to Surefire...")
   url = config.surefire_api["url"]
   headers = {
	  "apikey": config.surefire_api["apikey"],
	  "clientkey": config.surefire_api["clientkey"]
   }
   file_name = "contact_product_data " + str(year_month_day) + ".csv"
   files = {
	  "file": (file_name, open(file_name, "rb"), "text/csv")
   }
   payload = {"mappingtag": config.surefire_api["mappingtag"]}
   response = requests.post(url, files=files, data=payload, headers=headers)
   print(response.json())

def get_record_count():
	with open(file_name,"r") as f:
		reader = csv.reader(f,delimiter = ",")
		next(reader)
		all_csv_rows = list(reader)
		record_count = len(all_csv_rows)

	return record_count

def date_time_log():
	""" Log the date/time of the query or error. """

	# Write the current time to log.txt
	log.write("\n" + datetime.now().ctime() + "\n")

def execute(sf_object, query):
	""" Query the data with specific objects and SOQL statements. """

	try: # Try the query
		print("\n" + "Querying " + sf_object + " object...")
		data = sf_extract(sf_object, query)
		print("Writing " + sf_object + " data to File...")
		csv_writer(sf_object, data)
	except Exception as e: # If the query fails, log the results, date/time, and error
		log.write("\n" + "--! FAILED to query " + sf_object + " object !--"),date_time_log() 
		log.write("\n" + str(e) + "\n")
	else: # If the query is successful, log the results and date/time
		log.write("\n" + "-- Successful " + sf_object + " query --"),date_time_log()

#################### SALESFORCE QUERIES ####################

def query_financial_product_MO(query_date):
	# Drives through Financial Product to capture only Customer's with a registered Loan in Loantrac
	sf_object = "Bank_Account__c"
	query = "SELECT Owner.Id,Owner.Email,Primary_Customer__r.Id,Primary_Customer__r.FirstName,Primary_Customer__r.LastName,Primary_Customer__r.PersonEmail, \
	Primary_Customer__r.PersonBirthdate,Primary_Customer__r.PersonHomePhone,Primary_Customer__r.PersonMobilePhone,Primary_Customer__r.Phone, \
	Primary_Customer__r.PersonMailingStreet,Primary_Customer__r.PersonMailingCity,Primary_Customer__r.PersonMailingState, \
	Primary_Customer__r.PersonMailingPostalCode,Primary_Customer__r.CreatedDate,Opportunity__r.LeadID__c,Opportunity__r.Loss_Reason__c,Id,CreatedDate,Product__r.Name, \
	Loan_Purpose_Code__c,Mortgage_Loan_Type__c,Product_Type__c, \
	Funding_Amount__c,Lien_Position__c,Property_Address_SB__c,Current_Mortgage_Rate__c,Term__c,Mortgage_Status__c,Mortgage_Status_Date__c \
	FROM Bank_Account__c WHERE (Primary_Customer__c != null AND (RecordType.name = " + config.record_type["bank_account_mortgage_origination"] + " \
	or RecordType.name = " + config.record_type["bank_account_loan_account"] + ") AND Opportunity__r.RecordType.name = " + config.record_type["opportunity_mortgage_origination"] + ") \
	AND (" + str(query_date) + " or Primary_Customer__r." + str(query_date) + " or Opportunity__r." + str(query_date) + ")"
	execute(sf_object, query)

def query_account(query_date):
	# Drives through the Opportunity to capture only Customer's with 'Mortgage' record type Opportunities (NO FINANCIAL PRODUCT)
	sf_object = "Opportunity"
	query = "SELECT LeadSource,Owner.Id,Owner.Email,Account.Id,Account.FirstName,Account.LastName,Account.PersonEmail,Account.PersonBirthdate,Account.PersonHomePhone,\
	Account.PersonMobilePhone,Account.Phone,Account.PersonMailingStreet,Account.PersonMailingCity,Account.PersonMailingState,Account.PersonMailingPostalCode,Account.CreatedDate,LeadID__c,Loss_Reason__c \
	FROM Opportunity WHERE RecordType.name = " + str(config.record_type["opportunity_mortgage"]) + " AND (" \
	+ str(query_date) + " or Account." + str(query_date) + ")"
	execute(sf_object, query)

def query_contact(query_date):
	sf_object = "Contact"
	query = "SELECT Owner.Id,Owner.Email,Id,FirstName,LastName,Email,Birthdate,HomePhone,MobilePhone,Office_Phone__c,MailingStreet,MailingCity, \
	MailingState,MailingPostalCode,CreatedDate FROM Contact \
	WHERE RecordType.name = " + str(config.record_type["contact_referral"]) + " AND " + str(query_date)
	execute(sf_object, query)

def query_lead(query_date):
	sf_object = "Lead"
	query = "SELECT LeadSource,Owner.Id,Owner.Email,Id,FirstName,LastName,Email,Primary_Borrowers_Birthdate__c,Home_Phone__c,MobilePhone,Phone, \
	Street_Primary_Borrower__c,City_Primary_Borrower__c,State_Province_Primary_Borrower__c,Zip_Postal_Code_Primary_Borrower__c,CreatedDate \
	FROM Lead WHERE RecordType.name = " + str(config.record_type["lead_mortgage"]) + " AND \
	Status != 'Duplicate' AND IsConverted = False AND " + str(query_date)
	execute(sf_object, query)

#################### SALESFORCE QUERIES ####################

# Ensures that the program is run directly and not through a module
if __name__ == "__main__":

	# Set time variables for filtering logic in Salesforce
	now = datetime.now()
	year_month_day = now.strftime("%Y-%m-%d")
	utc_now = datetime.utcnow()
	run_time = utc_now.strftime("%Y-%m-%dT%H:%M:%SZ")

	# Define the name of the CSV file
	file_name = "contact_product_data " + str(year_month_day) + ".csv"

	# Initially write the CSV file headers
	with open(file_name, 'w+', encoding='utf-8') as csv_file:
		write_header = csv.writer(csv_file)
		write_header.writerow(config.csv_header)

	# Create the time_log file that will be used for the daily delta date comparison
	time_log = open("run_time.txt", "a")
	time_log.write(run_time + "\n")

	# Create the log file and write the time the program is run
	log = open("log.txt", "a")
	log.write("\n" + "|---------------------------------------|" + "\n") 
	log.write("PROGRAM STARTED: "),log.write(datetime.now().ctime())
	log.write("\n" + "|---------------------------------------|" + "\n")

	# Set the Salesforce username, password, and token
	sf = SalesforceBulk(username=config.salesforce["username"], password=config.salesforce["password"],
	sandbox=True, security_token=config.salesforce["token"])

	try:
		# Set the sftp hostkeys (if any)
		cnopts = pysftp.CnOpts()
		cnopts.hostkeys = None
	except Exception as e:
		pass
	else:
		pass

	# Set the sftp host, username, and password (optional paramter: port="22")
	sftp = pysftp.Connection(host=config.sftp["host"], username=config.sftp["username"],
	password=config.sftp["password"], cnopts=cnopts)

	# Build a dynamic User list, format the string, and create a variable that can be used in the SOQL filter
	sf_object = "User"
	query = "SELECT Id FROM User WHERE (UserRole.name LIKE 'HL Loan Officer%' OR UserRole.name LIKE 'HL Branch Manager%' \
	OR UserRole.name LIKE 'HL Area Manager%' OR UserRole.name LIKE 'HL Regional Manager%') AND IsActive = true"
	try:
		user_data = sf_extract(sf_object, query)
	except Exception as e:
		log.write("\n" + "--! FAILED to query " + sf_object + " object !--"),date_time_log() 
		log.write("\n" + str(e) + "\n")
	else: 
		log.write("\n" + "-- Successful " + sf_object + " query --"),date_time_log()
		with open("users.txt", 'w+') as users:
			for item in user_data:
				write_user_id = csv.DictWriter(users, item.keys())
				write_user_id.writerow(item)
		with open("users.txt") as users:
			users_list = users.readlines()
			users_list = list(map(str.strip,users_list))
			#users_list = ', '.join('{!r}'.format(ext_id) for ext_id in users_list)

	# Fire up the GUI
	app = QApplication(sys.argv)
	GUI = GUI()
	sys.exit(app.exec_())

# Close the SFTP connection and log files
sftp.close()
log.close()
time_log.close()
