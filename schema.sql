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
  -- 禁言：不是封鎖帳號，還是能登入、能讀、能看動態牆，只是不能再留新的領受
  -- （也不能編輯舊的）。只有永久管理員（ADMIN_LINE_USER_IDS）能操作，見
  -- auth.env_admin_required——一般輔導不行，這個動作要留給最高權限。
  is_muted boolean not null default false,
  created_at timestamptz not null default now()
);

create table if not exists daily_passages (
  id uuid primary key default gen_random_uuid(),
  group_id uuid not null references groups(id) on delete cascade,
  passage_date date not null default current_date,
  reference text not null,
  verses jsonb not null,
  -- 每一句對應的節號（像 '9:13'），跟 verses 一一對應，畫面上經文前面顯示節號用。
  -- 手動貼經文那條路沒有節號可以配，是 null，畫面上就不顯示節號。
  verse_labels jsonb,
  guiding_question text not null default '',
  created_by uuid references members(id) on delete set null,
  created_at timestamptz not null default now(),
  unique (group_id, passage_date)
);

create table if not exists reflections (
  id uuid primary key default gen_random_uuid(),
  passage_id uuid not null references daily_passages(id) on delete cascade,
  member_id uuid not null references members(id) on delete cascade,
  -- null = 只是讀過，沒有標記特定一句（「我也讀了」那個輕量按鈕）。
  -- 舊欄位，跟 verse_indexes[0] 保持同步，給還在用單一欄位的地方相容。
  verse_index int,
  -- 可以同時針對好幾句經文留一則領受，不是只能選一句；空陣列/null = 沒有標記任何一句。
  verse_indexes int[],
  note text not null default '',
  kind text not null default 'flower' check (kind in ('flower', 'fruit', 'butterfly', 'stone')),
  color text not null default '#EFC26B',
  created_at timestamptz not null default now()
  -- 沒有 unique (passage_id, member_id)：同一段經文可以留好幾則不同時間點的領受，
  -- 不會因為留過一次就被鎖住——回頭重讀有新的感動，本來就可以再留一則。
);

create table if not exists reflection_reactions (
  id uuid primary key default gen_random_uuid(),
  reflection_id uuid not null references reflections(id) on delete cascade,
  member_id uuid not null references members(id) on delete cascade,
  -- 固定的幾種反應，各自對應一句寫死的鼓勵語（合法值以 data_store.REACTION_KINDS
  -- 為準，set_reaction 會擋掉名單外的 kind）。刻意不在這裡加 CHECK 限制——之後想加
  -- 新的反應就不用每次都跑一次 migration 改 CHECK。不是自由留言，怕引發論戰。
  kind text not null,
  created_at timestamptz not null default now(),
  -- 一人對一則領受只能留一種反應，可以換，不會同時掛好幾個。
  unique (reflection_id, member_id)
);

create index if not exists idx_members_group on members (group_id);
create index if not exists idx_daily_passages_group_date on daily_passages (group_id, passage_date);
create index if not exists idx_reflections_passage on reflections (passage_id);
create index if not exists idx_reflection_reactions_reflection on reflection_reactions (reflection_id);

alter table groups enable row level security;
alter table members enable row level security;
alter table daily_passages enable row level security;
alter table reflections enable row level security;
alter table reflection_reactions enable row level security;
