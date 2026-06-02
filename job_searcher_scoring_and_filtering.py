# CONFIG — Edit this section to customise your search


JOB_SEARCHES = [
    ("data analyst",         "Melbourne"),
    ("data analyst",         "Sydney"),
    ("quantitative analyst", "Melbourne"),
    ("quantitative analyst", "Sydney"),
    # ("machine learning engineer", "Melbourne"),
    ("data scientist",            "Melbourne"),
    ("data scientist",            "Sydney"),
]

# Automatically built from JOB_SEARCHES
RELEVANT_TITLE_KEYWORDS = list(set(title.lower() for title, _ in JOB_SEARCHES))

# Extra related roles you'd also consider
EXTRA_RELEVANT_KEYWORDS = [
    "data scientist",
    "analytics consultant",
    "analytics analyst",
    "insights analyst",
    "quantitative researcher",
    "quantitative developer",
    "market risk",
    "data engineer",
    "decision analyst",
    "finance analyst",
]

RELEVANT_TITLE_KEYWORDS += EXTRA_RELEVANT_KEYWORDS

# Roles to filter out even if they appear in search results
IRRELEVANT_TITLE_KEYWORDS = [
    "inventory analyst",
    "fp&a",
    "financial planning",
    "credit analyst",
    "payroll",
    "hr analyst",
    "people analyst",
    "recruitment analyst",
    "sales analyst",
    "marketing analyst",
    "supply chain analyst",
    "procurement analyst",
    "logistics analyst",
    "quality analyst",
    "test analyst",
    "qa analyst",
    "accounts",
    "commercial analyst",
    "pricing analyst",
    "business intelligence",
    "bi analyst",
    "bi consultant",
    "bi developer",
    "reporting analyst",
    "business analyst",
    "enablement analyst",
    "campaign analyst",
    "market research associate",
    "marketplace analyst",
    "workforce analyst",
    "junior",
    "part time",
    "part-time",
]

PAGES_PER_SEARCH      = 3     # How many pages of results to scrape per search
OUTPUT_FILE           = "job_listings_260602.xlsx"
USE_SELENIUM          = True  # Set to True if requests get blocked or return empty results
DELAY_BETWEEN_PAGES   = 2     # Seconds to wait between page requests (be polite!)
DELAY_BETWEEN_SEARCHES= 3     # Seconds to wait between each search query

# ============================================================

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


# SALARY

def parse_salary(salary_str):
    """
    Handles formats like:
      - AUD 250000 - 300000 per annum
      - $149,833 – $167,903 per year
      - $130,000 + Super + Bonus
      - $80 - $85k plus super
      - $120000.00 - $135000.00 p.a.
      - $140,000 + superannuation
      - $200k + bonus
    """
    if not salary_str or salary_str in ("Not Listed", "N/A"):
        return 0

    cleaned = salary_str.lower()

    # Step 1: Expand 'k' shorthand FIRST before anything else is stripped
    cleaned = re.sub(r'(\d+\.?\d*)\s*k\b', lambda m: str(int(float(m.group(1)) * 1000)), cleaned)

    # Step 2: Strip currency symbols and noise
    cleaned = re.sub(r'(per annum|per year|per hour|per hr|p\.a\.?|aud|nzd|\$)', '', cleaned)
    cleaned = cleaned.replace(",", "").replace("–", "-")

    # Step 3: Strip everything after + (removes "+ super", "+ bonus" etc.)
    cleaned = re.sub(r'\+.*', '', cleaned)

    # Step 4: Extract plausible salary numbers (4–7 digits)
    numbers = re.findall(r'\b\d{4,7}(?:\.\d+)?\b', cleaned)
    numbers = [float(n) for n in numbers if 20_000 <= float(n) <= 1_000_000]

    if not numbers:
        # Fallback: try hourly rates (2–3 digit numbers)
        hourly = re.findall(r'\b\d{2,3}(?:\.\d+)?\b', cleaned)
        hourly = [float(n) for n in hourly if 20 <= float(n) <= 300]
        if not hourly:
            return 0
        return round(sum(hourly) / len(hourly) * 37.5 * 52)

    return round(sum(numbers) / len(numbers))


# RELEVANCE FILTER

def is_relevant(row):
    """
    Returns True if the job is relevant based on its title.
    - Filters OUT any title matching IRRELEVANT_TITLE_KEYWORDS
    - Keeps any title matching RELEVANT_TITLE_KEYWORDS (which includes JOB_SEARCHES)
    - Keeps unmatched titles by default (Seek's results are usually on-topic)
    """
    title = row.get("Job Title", "").lower()

    # Hard filter: if title matches an irrelevant keyword, always exclude
    for kw in IRRELEVANT_TITLE_KEYWORDS:
        if kw in title:
            return False, kw  # (is_relevant, reason)

    # Soft keep: if title matches a relevant keyword, always include
    for kw in RELEVANT_TITLE_KEYWORDS:
        if kw in title:
            return True, "matched relevant keyword"

    # Default: keep it (Seek results are generally on-topic)
    return True, "no keyword match — kept by default"


#  SCORING

def parse_days_ago(date_str):
    """Convert Seek's date string (e.g. '2d ago', '1h ago') to days as a float."""
    if not date_str or date_str == "N/A":
        return 999
    date_str = date_str.lower().strip()
    match = re.search(r'(\d+)\s*(h|d|m)', date_str)
    if match:
        value, unit = int(match.group(1)), match.group(2)
        if unit == 'h':  return value / 24
        if unit == 'd':  return float(value)
        if unit == 'm':  return value * 30
    return 999


def score_job(row):
    title   = row.get("Job Title", "").lower()
    company = row.get("Company",   "").lower()
    salary  = parse_salary(row.get("Salary", ""))

    # --- SALARY FLOOR (so high-paying roles can't be buried by other factors) ---
    if salary >= 200_000:
        score = 60
    elif salary >= 150_000:
        score = 40
    else:
        score = 0

    # --- 1. SALARY SCORE (50 points) ---
    if salary >= 250_000:   score += 50
    elif salary >= 200_000: score += 45
    elif salary >= 180_000: score += 38
    elif salary >= 160_000: score += 32
    elif salary >= 140_000: score += 26
    elif salary >= 120_000: score += 20
    elif salary >= 100_000: score += 13
    elif salary >= 80_000:  score += 7
    elif salary > 0:        score += 3

    # --- 2. SENIORITY (15 points) ---
    if any(kw in title for kw in ["principal", "director", "head of", "vp ", "vice president", "chief"]):
        score += 15
    elif any(kw in title for kw in ["senior", "lead", "manager", "sr.", "consultant",
                                     "advisor", "adviser", "specialist", "expert"]):
        score += 10
    elif any(kw in title for kw in ["mid", "intermediate"]):
        score += 6
    elif any(kw in title for kw in ["junior", "graduate", "entry", "associate", "cadet"]):
        score += 2
    else:
        score += 5

    # --- 3. RECENCY (15 points) ---
    days_old = parse_days_ago(row.get("Date Posted", ""))
    if days_old <= 1:    score += 15
    elif days_old <= 3:  score += 12
    elif days_old <= 7:  score += 8
    elif days_old <= 14: score += 4

    # --- 4. INDUSTRY (5 points) ---
    high_value = [
        "macquarie", "commonwealth", "westpac", "anz", "nab", "citibank",
        "qbe", "allianz", "suncorp", "axa",
        "blackrock", "vanguard", "fidelity",
        "google", "amazon", "microsoft", "meta", "apple",
        "deloitte", "pwc", "kpmg", "mckinsey", "accenture", "ey ", "ernst",
    ]
    if any(kw in company for kw in high_value):
        score += 5

    # --- 5. SALARY TRANSPARENCY (10 points) ---
    if row.get("Salary", "Not Listed") != "Not Listed":
        score += 10

    return score


def assign_tier(score):
    if score >= 80:   return "⭐ Top Pick"
    elif score >= 60: return "✅ Strong"
    elif score >= 40: return "👍 Good"
    elif score >= 20: return "⚠️ Average"
    else:             return "❌ Low Priority"


#  SCRAPING

def parse_job_cards(soup, job_title, location):
    """Extract job data from a parsed BeautifulSoup page."""
    jobs = []
    job_cards = soup.find_all("article", {"data-card-type": "JobCard"})

    for card in job_cards:
        title_tag    = card.find("a",    {"data-automation": "jobTitle"})
        company_tag  = card.find("a",    {"data-automation": "jobCompany"})
        location_tag = card.find("a",    {"data-automation": "jobLocation"})
        salary_tag   = card.find("span", {"data-automation": "jobSalary"})
        date_tag     = card.find("span", {"data-automation": "jobListingDate"})

        jobs.append({
            "Job Title":    title_tag.get_text(strip=True)    if title_tag    else "N/A",
            "Company":      company_tag.get_text(strip=True)  if company_tag  else "N/A",
            "Location":     location_tag.get_text(strip=True) if location_tag else location,
            "Salary":       salary_tag.get_text(strip=True)   if salary_tag   else "Not Listed",
            "Date Posted":  date_tag.get_text(strip=True)     if date_tag     else "N/A",
            "Search Query": job_title,
            "URL":          "https://www.seek.com.au" + title_tag["href"] if title_tag else "N/A",
        })

    return jobs


def scrape_with_requests(job_title, location, pages):
    """Scrape using simple HTTP requests (faster, may be blocked)."""
    import random
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    ]
    def get_headers():
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-AU,en;q=0.9",
            "Referer": "https://www.seek.com.au/",
        }

    jobs    = []
    query   = job_title.replace(" ", "-")
    loc     = location.lower()
    session = requests.Session()
    session.get("https://www.seek.com.au/", headers=get_headers(), timeout=10)
    time.sleep(random.uniform(2, 4))

    for page in range(1, pages + 1):
        url = f"https://www.seek.com.au/{query}-jobs/in-{loc}?page={page}"
        print(f"  Fetching page {page}: {url}")
        try:
            response = session.get(url, headers=get_headers(), timeout=10)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"  Error on page {page}: {e}")
            print("  Tip: Try setting USE_SELENIUM = True in the config.")
            break

        soup      = BeautifulSoup(response.text, "html.parser")
        page_jobs = parse_job_cards(soup, job_title, location)

        if not page_jobs:
            print(f"  No results on page {page} — stopping early.")
            break

        jobs.extend(page_jobs)
        time.sleep(random.uniform(DELAY_BETWEEN_PAGES, DELAY_BETWEEN_PAGES + 2))

    return jobs


def scrape_with_selenium(job_title, location, pages):
    """Scrape using Selenium (slower but handles JS-rendered pages)."""
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager

    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(f"user-agent={HEADERS['User-Agent']}")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    jobs   = []
    query  = job_title.replace(" ", "-")
    loc    = location.lower()

    try:
        for page in range(1, pages + 1):
            url = f"https://www.seek.com.au/{query}-jobs/in-{loc}?page={page}"
            print(f"  Loading page {page}: {url}")
            driver.get(url)

            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "article[data-card-type='JobCard']")
                    )
                )
            except Exception:
                print(f"  Timed out on page {page} — stopping early.")
                break

            soup      = BeautifulSoup(driver.page_source, "html.parser")
            page_jobs = parse_job_cards(soup, job_title, location)

            if not page_jobs:
                print(f"  No results on page {page} — stopping early.")
                break

            jobs.extend(page_jobs)
            time.sleep(DELAY_BETWEEN_PAGES)
    finally:
        driver.quit()

    return jobs


#  OUTPUT

def save_to_excel(df_relevant, df_filtered, output_file):
    """Save results to Excel with separate sheets for relevant and filtered jobs."""
    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:

        # Main sheet — ranked relevant jobs
        df_relevant.to_excel(writer, index=False, sheet_name="Relevant Jobs")

        # One sheet per search query
        for query in df_relevant["Search Query"].unique():
            sheet_name = query.title().replace(" ", "_")[:31]
            df_relevant[df_relevant["Search Query"] == query].to_excel(
                writer, index=False, sheet_name=sheet_name)

        # Filtered out jobs — for transparency so you can check what was removed
        if not df_filtered.empty:
            df_filtered.to_excel(writer, index=False, sheet_name="Filtered Out")

        # Auto-fit column widths
        for sheet in writer.sheets.values():
            for col in sheet.columns:
                max_len = max((len(str(cell.value or "")) for cell in col), default=10)
                sheet.column_dimensions[col[0].column_letter].width = min(max_len + 4, 60)

    print(f"\nSaved to '{output_file}'")


#  MAIN

def main():
    if not JOB_SEARCHES:
        print("No searches configured. Add entries to JOB_SEARCHES in the config section.")
        return

    scrape_fn = scrape_with_selenium if USE_SELENIUM else scrape_with_requests
    all_jobs  = []

    for job_title, location in JOB_SEARCHES:
        print(f"\n=== Searching: '{job_title}' in {location} ===")
        results = scrape_fn(job_title, location, PAGES_PER_SEARCH)
        print(f"  Found {len(results)} listing(s).")
        all_jobs.extend(results)
        time.sleep(DELAY_BETWEEN_SEARCHES)

    if not all_jobs:
        print("\nNo jobs found. Try enabling USE_SELENIUM = True or check your search terms.")
        return

    df = pd.DataFrame(all_jobs).drop_duplicates(subset=["Job Title", "Company", "Location"])

    # --- Apply relevance filter ---
    relevance         = df.apply(is_relevant, axis=1)
    df["_relevant"]   = relevance.apply(lambda x: x[0])
    df["Filter Reason"] = relevance.apply(lambda x: x[1] if not x[0] else "")

    df_relevant = df[df["_relevant"]].drop(columns=["_relevant", "Filter Reason"]).copy()
    df_filtered = df[~df["_relevant"]].drop(columns=["_relevant"]).copy()

    print(f"\nTotal scraped:  {len(df)}")
    print(f"Relevant jobs:  {len(df_relevant)}")
    print(f"Filtered out:   {len(df_filtered)}")

    if not df_filtered.empty:
        print("\nFiltered out:")
        for _, row in df_filtered.iterrows():
            print(f"  ✗ {row['Job Title']} at {row['Company']}  (reason: {row['Filter Reason']})")

    # --- Apply scoring to relevant jobs only ---
    df_relevant["Salary (Estimated $)"] = df_relevant.apply(lambda r: parse_salary(r["Salary"]), axis=1)
    df_relevant["Score"]                = df_relevant.apply(score_job, axis=1)
    df_relevant["Priority Tier"]        = df_relevant["Score"].apply(assign_tier)
    df_relevant = df_relevant.sort_values("Score", ascending=False).reset_index(drop=True)
    df_relevant.insert(0, "Rank", df_relevant.index + 1)

    print(f"\nTop 10 jobs by score:")
    print(df_relevant[["Rank", "Job Title", "Company", "Salary", "Score", "Priority Tier"]].head(10).to_string(index=False))

    save_to_excel(df_relevant, df_filtered, OUTPUT_FILE)


if __name__ == "__main__":
    main()