export interface Class {
  id: number;
  name: string;
  level: string;
  academic_year: string;
  student_count?: number;
  average_grade?: number;
  subjects?: Subject[];
  created_at: string;
}

export interface Subject {
  id: number;
  name: string;
  teacher: string;
}