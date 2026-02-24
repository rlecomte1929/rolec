-- Option 6B: Enable Supabase Realtime for notifications table.
-- Realtime respects RLS: users only receive events for rows they can select.

do $$
begin
  alter publication supabase_realtime add table public.notifications;
exception
  when duplicate_object then
    null; -- table already in publication
end
$$;
