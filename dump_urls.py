from ugc_db.db_manager import SessionLocal, Influencer

def dump_urls():
    db = SessionLocal()
    influencers = db.query(Influencer).all()
    for inf in influencers:
        print(f"Name: {inf.name}")
        print(f"URL:  {inf.reference_image_url}")
        print("-" * 20)
    db.close()

if __name__ == "__main__":
    dump_urls()
