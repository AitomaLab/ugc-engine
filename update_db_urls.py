from ugc_db.db_manager import SessionLocal, Influencer

def update_db_urls():
    db = SessionLocal()
    
    # Update Meg
    meg = db.query(Influencer).filter(Influencer.name == "Meg").first()
    if meg:
        old_url = meg.reference_image_url
        new_url = "/influencers/meg.jpg" # Local path in frontend/public
        meg.reference_image_url = new_url
        print(f"Updated Meg: {old_url} -> {new_url}")

    # Update Max
    max_inf = db.query(Influencer).filter(Influencer.name == "Max").first()
    if max_inf:
        old_url = max_inf.reference_image_url
        new_url = "/influencers/max.jpg" # Local path in frontend/public
        max_inf.reference_image_url = new_url
        print(f"Updated Max: {old_url} -> {new_url}")
        
    db.commit()
    db.close()

if __name__ == "__main__":
    update_db_urls()
