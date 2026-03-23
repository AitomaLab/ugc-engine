import { supabase } from './supabaseClient';

export async function createProject(data: { name: string; description?: string }) {
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) throw new Error('Not authenticated');
  const { data: project, error } = await supabase
    .from('projects')
    .insert({ name: data.name, description: data.description, user_id: user.id })
    .select()
    .single();
  if (error) throw error;
  return project;
}

export async function updateProject(id: string, data: { name: string; description?: string }) {
  const { data: project, error } = await supabase
    .from('projects')
    .update({ name: data.name, description: data.description })
    .eq('id', id)
    .select()
    .single();
  if (error) throw error;
  return project;
}
