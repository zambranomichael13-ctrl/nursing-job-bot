import os
import json
import aiohttp
import discord
from dotenv import load_dotenv

load_dotenv()

JOOBLE_API_KEY = os.getenv("JOOBLE_API_KEY")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))

JOOBLE_URL = f"https://jooble.org/api/{JOOBLE_API_KEY}"

RESULTS_PER_PAGE = 50
SEARCH_LOCATION = "Ontario, CA"
SEARCH_RADIUS = "40"

CITIES = {
    "Ontario",
    "Rancho Cucamonga",
    "Fontana",
    "Upland",
    "Riverside",
    "San Bernardino",
    "Loma Linda",
    "Redlands",
    "Corona",
    "Pomona",
    "Chino",
    "Chino Hills",
    "Colton",
    "Rialto",
}

NEW_GRAD_TERMS = [
    "new grad",
    "new graduate",
    "new-graduate",
    "graduate nurse",
    "rn residency",
    "rn resident",
    "nurse residency",
    "residency program",
    "new rn",
    "entry level",
    "entry-level",
]

POSTED_FILE = "jooble_posted_jobs.json"


def load_posted_jobs():
    if not os.path.exists(POSTED_FILE):
        return set()

    try:
        with open(POSTED_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:
        return set()


def save_posted_jobs(posted_jobs):
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(posted_jobs), f, indent=2)


def normalize_city(location):
    location_lower = location.lower()

    for city in CITIES:
        if city.lower() in location_lower:
            return city

    return None


def is_new_grad(job):
    title = job.get("title", "").lower()
    snippet = job.get("snippet", "").lower()
    company = job.get("company", "").lower()

    text = f"{title} {snippet} {company}"

    return any(term in text for term in NEW_GRAD_TERMS)


async def get_jobs():
    payload = {
        "keywords": "RN Registered Nurse",
        "location": SEARCH_LOCATION,
        "radius": SEARCH_RADIUS,
        "page": 1,
        "ResultOnPage": RESULTS_PER_PAGE,
        "companysearch": False,
    }

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                JOOBLE_URL,
                json=payload,
                headers=headers
            ) as response:

                print(f"Jooble API Status: {response.status}")

                if response.status != 200:
                    print(await response.text())
                    return []

                data = await response.json()

    except Exception as e:
        print(f"Jooble API connection error: {e}")
        return []

    jobs = data.get("jobs", [])

    print(f"Jooble returned {len(jobs)} jobs.")

    filtered_jobs = []

    for job in jobs:
        location = job.get("location", "")
        city = normalize_city(location)

        if city:
            job["detected_city"] = city
            filtered_jobs.append(job)

    return filtered_jobs


def create_embed(job):
    title = job.get("title", "Registered Nurse")
    company = job.get("company", "Unknown Company")
    location = job.get("location", "Unknown Location")
    salary = job.get("salary", "")
    job_type = job.get("type", "")
    snippet = job.get("snippet", "")
    link = job.get("link")

    embed = discord.Embed(
        title=title,
        description=f"**Company:** {company}\n**Location:** {location}",
        url=link if link else discord.Embed.Empty,
    )

    if job.get("detected_city"):
        embed.add_field(
            name="📍 City",
            value=job["detected_city"],
            inline=True,
        )

    if job_type:
        embed.add_field(
            name="💼 Type",
            value=job_type,
            inline=True,
        )

    if salary:
        embed.add_field(
            name="💰 Salary",
            value=salary,
            inline=True,
        )

    if is_new_grad(job):
        embed.add_field(
            name="🎓 New Grad / Residency",
            value="Likely",
            inline=False,
        )

    if snippet:
        cleaned_snippet = (
            snippet
            .replace("<b>", "")
            .replace("</b>", "")
        )

        if len(cleaned_snippet) > 500:
            cleaned_snippet = cleaned_snippet[:500] + "..."

        embed.add_field(
            name="Description",
            value=cleaned_snippet,
            inline=False,
        )

    if link:
        embed.add_field(
            name="Apply",
            value=f"[View Job / Apply]({link})",
            inline=False,
        )

    embed.set_footer(text="Job source: Jooble")

    return embed


async def run_job_check():
    posted_jobs = load_posted_jobs()

    print("\nChecking Jooble for RN jobs...")

    jobs = await get_jobs()

    print(f"Inland Empire RN jobs found: {len(jobs)}")

    if not jobs:
        print("No Inland Empire RN jobs found.")
        return

    new_jobs = []

    for job in jobs:
        job_id = job.get("id")

        if job_id is None:
            continue

        unique_id = f"jooble_{job_id}"

        if unique_id not in posted_jobs:
            new_jobs.append((job, unique_id))

    print(f"New jobs: {len(new_jobs)}")

    if not new_jobs:
        print("No new jobs to post.")
        return

    intents = discord.Intents.default()

    client = discord.Client(intents=intents)

    try:
        await client.login(DISCORD_TOKEN)

        channel = await client.fetch_channel(CHANNEL_ID)

        posted_count = 0

        for job, unique_id in new_jobs:
            try:
                embed = create_embed(job)

                await channel.send(embed=embed)

                posted_jobs.add(unique_id)
                posted_count += 1

                print(
                    f"Posted: {job.get('title')} | "
                    f"{job.get('company')} | "
                    f"{job.get('location')}"
                )

            except Exception as e:
                print(f"Error posting job: {e}")

        save_posted_jobs(posted_jobs)

        print(f"Posted {posted_count} new jobs.")

    finally:
        await client.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_job_check())
