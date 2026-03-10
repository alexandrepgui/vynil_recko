-- Seed a default local dev user: dev@groovelog.local / password123
INSERT INTO auth.users (
  id, instance_id, aud, role, email,
  encrypted_password, email_confirmed_at,
  created_at, updated_at, confirmation_token,
  recovery_token, email_change, email_change_token_new,
  email_change_token_current, reauthentication_token,
  raw_app_meta_data, raw_user_meta_data, is_super_admin
) VALUES (
  'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
  '00000000-0000-0000-0000-000000000000',
  'authenticated', 'authenticated', 'dev@groovelog.local',
  crypt('password123', gen_salt('bf')),
  now(), now(), now(), '',
  '', '', '', '', '',
  '{"provider":"email","providers":["email"]}',
  '{}', false
) ON CONFLICT (id) DO NOTHING;

INSERT INTO auth.identities (
  id, user_id, identity_data, provider, provider_id,
  created_at, updated_at, last_sign_in_at
) VALUES (
  'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
  'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
  jsonb_build_object('sub', 'a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'email', 'dev@groovelog.local'),
  'email', 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
  now(), now(), now()
) ON CONFLICT (provider_id, provider) DO NOTHING;
