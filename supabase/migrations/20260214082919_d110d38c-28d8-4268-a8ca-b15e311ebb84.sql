
-- Block all SELECT access to waitlist_submissions
-- No one needs to read this data via the API; admin access is through Lovable Cloud backend UI
CREATE POLICY "No public read access"
  ON public.waitlist_submissions
  FOR SELECT
  USING (false);
