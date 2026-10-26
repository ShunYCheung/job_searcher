# Job Searcher

Python script to scrape the SEEK listings for specific search words. The format of the search words is <position_title>, <location>. For example, Data analyst, Sydney.

The script returns a .csv file with job listings. The script lists the job description by score in descending order. 

The score takes the following factors into account:
- Salary
- Keywords
- Seniority
- Well known companies (Commonwealth Bank, Amazon .etc)

The script has a scoring system which upweight relevant keywords and downweight irrelevant keywords. You can edit the list of 'relevant keywords' and 'irrelevant keywords' to suit your preferences. 

You can also change the scoring for the different factors. For example, you may aim for a specific seniority (for example "Senior" position) and you may assign "Senior" with the highest score. 
