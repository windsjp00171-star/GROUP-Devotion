-- GROUP-Devotion 資料庫結構
-- 一個小組、一段經文、留下的領受。
--
-- RLS：四張表都開啟 RLS，但刻意不加任何 policy——只有 Flask 後端用
-- service role key 存取（略過 RLS），前端不會直接打 Supabase，
-- anon / authenticated 角色預設一律被拒絕。

create extension if not exists "pgcrypto";

create table if not exists groups (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  created_at timestamptz not null default now()
);

create table if not exists members (
  id uuid primary key default gen_random_uuid(),
  group_id uuid not null references groups(id) on delete cascade,
  line_user_id text not null unique,
  display_name text not null default '',
  picture_url text,
  -- 自己設定的暱稱，留空就顯示 LINE 的 display_name。
  -- 不是本名也可以，讓還沒準備好用真名分享的人多一個選擇。
  nickname text,
  -- 輔導：可以進 /admin 排經文。ADMIN_LINE_USER_IDS 環境變數設定的是
  -- 永久管理員，不受這個欄位影響；這個欄位是「後台可以指定誰是輔導」
  -- 那種可以隨時開關的一般輔導。
  is_leader boolean not null default false,
  created_at timestamptz not null default now()
);

create table if not exists daily_passages (
  id uuid primary key default gen_random_uuid(),
  group_id uuid not null references groups(id) on delete cascade,
  passage_date date not null default current_date,
  reference text not null,
  verses jsonb not null,
  guiding_question text not null default '',
  created_by uuid references members(id) on delete set null,
  created_at timestamptz not null default now(),
  unique (group_id, passage_date)
);

create table if not exists reflections (
  id uuid primary key default gen_random_uuid(),
  passage_id uuid not null references daily_passages(id) on delete cascade,
  member_id uuid not null references members(id) on delete cascade,
  -- null = 只是讀過，沒有標記特定一句（「我也讀了」那個輕量按鈕）
  verse_index int,
  note text not null default '',
  kind text not null default 'flower' check (kind in ('flower', 'fruit', 'butterfly', 'stone')),
  color text not null default '#EFC26B',
  created_at timestamptz not null default now(),
  unique (passage_id, member_id)
);

create index if not exists idx_members_group on members (group_id);
create index if not exists idx_daily_passages_group_date on daily_passages (group_id, passage_date);
create index if not exists idx_reflections_passage on reflections (passage_id);

alter table groups enable row level security;
alter table members enable row level security;
alter table daily_passages enable row level security;
alter table reflections enable row level security;
