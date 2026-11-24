import os
import re
import logging
import time  # Naya import retry delay (sleep) ke liye
from dotenv import load_dotenv

load_dotenv()

from app.agent.email_agent import EmailAgent, RankedArticleDetail, EmailDigestResponse
from app.agent.curator_agent import CuratorAgent
from app.profiles.user_profile import USER_PROFILE
from app.database.repository import Repository
from app.services.email import send_email, digest_to_html

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def generate_email_digest(hours: int = 24, top_n: int = 10) -> EmailDigestResponse:
    curator = CuratorAgent(USER_PROFILE)
    email_agent = EmailAgent(USER_PROFILE)
    repo = Repository()
    
    digests = repo.get_recent_digests(hours=hours)
    total = len(digests)
    
    if total == 0:
        logger.warning(f"No digests found from the last {hours} hours")
        raise ValueError("No digests available")
    
    logger.info(f"Ranking {total} digests for email generation")
    ranked_articles = curator.rank_digests(digests)
    
    if not ranked_articles:
        logger.error("Failed to rank digests")
        raise ValueError("Failed to rank articles")
    
    logger.info(f"Generating email digest with top {top_n} articles")
    
    article_details = [
        RankedArticleDetail(
            digest_id=a.digest_id,
            rank=a.rank,
            relevance_score=a.relevance_score,
            reasoning=a.reasoning,
            title=next((d["title"] for d in digests if d["id"] == a.digest_id), ""),
            summary=next((d["summary"] for d in digests if d["id"] == a.digest_id), ""),
            url=next((d["url"] for d in digests if d["id"] == a.digest_id), ""),
            article_type=next((d["article_type"] for d in digests if d["id"] == a.digest_id), "")
        )
        for a in ranked_articles
    ]
    
    email_digest = email_agent.create_email_digest_response(
        ranked_articles=article_details,
        total_ranked=len(ranked_articles),
        limit=top_n
    )
    
    logger.info("Email digest generated successfully")
    logger.info(f"\n=== Email Introduction ===")
    logger.info(email_digest.introduction.greeting)
    logger.info(f"\n{email_digest.introduction.introduction}")
    
    return email_digest


def send_digest_email(hours: int = 24, top_n: int = 10) -> dict:
    try:
        result = generate_email_digest(hours=hours, top_n=top_n)
        markdown_content = result.to_markdown()
        html_content = digest_to_html(result)
        
        subject = f"Daily AI News Digest - {result.introduction.greeting.split('for ')[-1] if 'for ' in result.introduction.greeting else 'Today'}"
        
        # --- NAYA DATABASE LOGIC ---
        repo = Repository()
        db_recipients = repo.get_all_recipients()
        
        recipients_list = []
        
        if db_recipients:
            # 1. Agar DB mein log hain, toh unke proper names aur emails uthao
            for r in db_recipients:
                recipients_list.append({"email": r.email, "name": r.name})
        else:
            # 2. BACKUP: Agar DB khali hai, toh .env se uthao aur purana name guess karne wala logic lagao
            emails_string = os.getenv("RECEIVER_EMAILS", os.getenv("MY_EMAIL", ""))
            env_emails = [e.strip() for e in emails_string.split(",") if e.strip()]
            
            for email in env_emails:
                username = email.split('@')[0]
                name_without_numbers = re.sub(r'\d+', '', username)
                clean_name = name_without_numbers.replace('.', ' ').replace('_', ' ').strip().title()
                recipients_list.append({"email": email, "name": clean_name or "Friend"})

        successful_emails = 0
        max_retries = 3  # Add kiya gaya hai taake loop kitni baar retry kare yeh specify ho sake
        
        # 3. Email bhejne ka Loop with Retry Logic
        for person in recipients_list:
            email_address = person["email"]
            user_name = person["name"]
            
            # Personalization (VIP Name Entry)
            personalized_html = f'<h2 style="color: #2c3e50;">Hello {user_name},</h2>\n' + html_content
            personalized_text = f"Hello {user_name},\n\n" + markdown_content

            # Ab seedha fail nahi hoga, balkay 3 attempts karega
            for attempt in range(1, max_retries + 1):
                try:
                    send_email(
                        subject=subject,
                        body_text=personalized_text,
                        body_html=personalized_html,
                        recipients=[email_address]
                    )
                    
                    logger.info(f"Email sent successfully to: {user_name} ({email_address})")
                    successful_emails += 1
                    break  # Success ho gaya toh retry loop se bahar aa jao aur next email pe chalo
                    
                except Exception as e:
                    logger.warning(f"Attempt {attempt}/{max_retries} failed for {email_address}: {e}")
                    if attempt < max_retries:
                        time.sleep(5)  # 5 seconds wait kar ke dobara try karein
                    else:
                        logger.error(f"Failed to send email to {email_address} after {max_retries} attempts.")
        
        return {
            "success": True if successful_emails > 0 else False,
            "subject": subject,
            "articles_count": len(result.articles),
            "emails_sent": successful_emails
        }
    except Exception as e:
        logger.error(f"Error in email processing: {e}")
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    result = send_digest_email(hours=24, top_n=10)
    if result.get("success"):
        print("\n=== Email Digest Sent ===")
        print(f"Subject: {result.get('subject')}")
        print(f"Emails Sent: {result.get('emails_sent')}")
    else:
        print(f"Error: {result.get('error')}")