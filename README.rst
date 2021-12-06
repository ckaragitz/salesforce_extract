Salesforce Extractor 
=======

Disclaimer
-----------
This code was built for a very specific use case: query salesforce objects, save them to CSV files, transform the data (in this case, append fields and values), and push the data via SFTP.

*You can reuse bits and pieces of this code to create your own solution*

All successful queries will be written to log.txt alongside any errors and the traceback call.

Setup
-----

1. 'git clone' this repository
2. install the requirements of the repository with the command `pip install -r requirements.txt`
3. plug in your Salesforce credentials and SFTP server credentials in the config.py file (this SFTP part is not required if you are not using this feature)
4. declare the object you want to query, define your SOQL statement, and give the output file a name
5. run the code!

Description
-----------

This Python script will query a set of objects in Salesforce, save the results in separate CSV files, transform the data, and then push the data via SFTP to a designated server/site.

It was originally built to save time and energy since each object in Salesforce needs to be queried separately. Instead of querying each object in Data Loader, run the script, save the results, and then do what you wish from there. 

It's simple: Plug and Play.

salesforce_extract_v2
=======
A complete revamp of the original salesforce_extract project. This was my finalized version with added features. Leaving the other one up for simplicity purposes as this is a more advanced script.

This version of the application provides a user friendly GUI to set the query parameters. It also sends the data directly to a marketing solution.
