-- Run once in the Supabase dashboard: Database > SQL Editor > New query.
-- plan.md §14 Deepthi track — Google OAuth + Supabase.
--
-- Supabase Auth already maintains auth.users for every sign-in (Google
-- included), but that table is managed by Supabase and not meant for app
-- joins. This adds an app-level `profiles` table keyed 1:1 on auth.users.id,
-- which is what Abel's /history table should foreign-key against.

create table if not exists public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  email text,
  full_name text,
  avatar_url text,
  created_at timestamptz not null default now()
);

alter table public.profiles enable row level security;

create policy "Users can read their own profile"
  on public.profiles for select
  using (auth.uid() = id);

create policy "Users can update their own profile"
  on public.profiles for update
  using (auth.uid() = id);

-- Auto-create a profile row the first time someone signs in (Google OAuth
-- included), so there's always a profiles row for a history table to point
-- a foreign key at.
create or replace function public.handle_new_user()
returns trigger as $$
begin
  insert into public.profiles (id, email, full_name, avatar_url)
  values (
    new.id,
    new.email,
    new.raw_user_meta_data ->> 'full_name',
    new.raw_user_meta_data ->> 'avatar_url'
  )
  on conflict (id) do nothing;
  return new;
end;
$$ language plpgsql security definer set search_path = public;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

-- plan.md §14 Abel track — one row per answered /ask query. `user_id`
-- defaults to auth.uid() so the backend (prototype/ask_service/history.py)
-- never has to send it explicitly: it just POSTs with the caller's own
-- session token and PostgREST resolves the JWT for us, same trust boundary
-- as auth.py's /me.
create table if not exists public.history (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references public.profiles (id) on delete cascade,
  query text not null,
  intent text,
  city text,
  lang text,
  response text,
  created_at timestamptz not null default now()
);

alter table public.history enable row level security;

create policy "Users can read their own history"
  on public.history for select
  using (auth.uid() = user_id);

create policy "Users can insert their own history"
  on public.history for insert
  with check (auth.uid() = user_id);

-- Users own their history: DELETE /history clears it (data-privacy review,
-- plan.md §8 Phase 6). No update policy — rows are append-only otherwise.
create policy "Users can delete their own history"
  on public.history for delete
  using (auth.uid() = user_id);
