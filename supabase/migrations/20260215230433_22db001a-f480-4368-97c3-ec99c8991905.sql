
-- Block all UPDATE access on waitlist_submissions
CREATE POLICY "No public update access"
  ON public.waitlist_submissions
  FOR UPDATE
  USING (false);

-- Block all DELETE access on waitlist_submissions
CREATE POLICY "No public delete access"
  ON public.waitlist_submissions
  FOR DELETE
  USING (false);
