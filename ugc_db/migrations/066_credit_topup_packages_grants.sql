-- PostgREST must see new tables; grants match other catalog tables.
GRANT ALL ON TABLE public.credit_topup_packages TO service_role;
GRANT SELECT ON TABLE public.credit_topup_packages TO anon, authenticated;

NOTIFY pgrst, 'reload schema';
