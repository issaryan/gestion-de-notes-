export interface Grade {
  id: number;
  student_id: number;
  subject_id: number;
  grade: number;
  evaluation_date: string;
  comments?: string;
  created_at: string;
  subject?: string;
  teacher_name?: string;
}