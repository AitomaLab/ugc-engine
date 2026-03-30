-- Fix legacy 'influencers_name_key' constraint
-- The 'name' column was originally globally unique, which breaks multi-tenancy.
-- We must drop the global unique constraint so different users can have identical influencer names
-- (e.g., seeding the default templates like 'Lila' into multiple projects).

ALTER TABLE influencers 
DROP CONSTRAINT IF EXISTS influencers_name_key;

-- If you still want to prevent the SAME user from creating duplicate names in the SAME project, 
-- you can optionally add this constraint instead:
-- ALTER TABLE influencers ADD CONSTRAINT influencers_name_project_key UNIQUE (name, project_id);
