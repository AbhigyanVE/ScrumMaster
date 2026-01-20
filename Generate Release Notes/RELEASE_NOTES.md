# Release Notes

## Version 1
- INFO: Shifting to JIRA successful, This is the checkpoint to verify wheather the data is fetched from JIRA or not

## Version 1.1
- IMPROVEMENTS: Extraction of Project Data in JSON was sucessfull, but the data was conjugated in 1 single JSON, hence JSONs folder contains JSON data for every project individually

## Version 2
- IMPROVEMENTS: Solving Objectves of Phase 2. 1: Strucutred outputs using pydantic models. 2: Agent personas with role and context. 3: Task templates for different scrum master functions. 4: Context for conversations (this is not yet working).

## Version 1.2
- IMPROVEMENTS: Added the DB

## Version 2.1
- IMPROVEMENTS: There was a slight problem with JIRA, due to which the ISSUE COUNT was shown as 0 in the JSON, the issue is fixed now but there is a quirk in JIRA on how it handles the ISSUE COUNT hence JIRA shows issue count as 0, but during data extraction, the code counts and hence the actual count is adjusted there

## Version 2.2
- IMPROVEMENTS: When the query is kind of a greeting or a general query, the SQL is not triggered and also sometimes the LLM might also not be triggered for these kind of queries. The next improvement is, when asked for listing team members or listing projects the SQL response was fine but the response from the LLM was not acceptable, this is also fixed now

## Version 3
- IMPROVEMENTS: FRONTEND ENHANCEMENTS - APPLICATION VERSION on the main interface, BRANDING LOGO on Sidebar, Redesigned the QUICK STATS section, Improved overall UI of Sidebar

## Version 3.1
- IMPROVEMENTS: Added README

## Version 3.1.1
- CRITICAL BUG FIXES: The 'duedate' or the deadlines for an issue was not being extracted from Jira, therefore, when asked for the deadline of an issue, the bot replies with the last updated date instead (Notes pt.5). The other issue was with the CONTEXT, whenever the user queries with any farewell message, then the bot used to clear the JSON context but the LLM still holded the previous context, from this version onwards this issue seems to be fixed (Notes pt.6)

## Version 3.1.2
- IMPROVEMENTS: Added the Functionality for CRON Job. Server Deployment

## Version 3.1.3
- IGNORE. Its just an interval change

## Version 3.2
- ADDITION: Added the streamlit config file

## Version 3.2.1
- UPDATE: The function of deleting the JSONs folder which was implemeted in the previous version was not working correctly hence it was updated

## Version 3.2.2
- IMPROVEMENTS: Added 'main_for_server.py' to run the complete pipeline using 'pm2' instead of nohup. The commands can be found in NOTES

## Version 3.3
- IMPROVEMENTS: The description column has been added and is working with the integration. BUG: LLM's current date and time is very backdated hence need to be fixed

## Version 3.3.1
- Forgot to Change the Version in Streamlit App Display

## Version 3.4
- Updated the ReadMe and my personal notes

