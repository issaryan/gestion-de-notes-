import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { Grade } from '../models/grade.model';
import { environment } from '../../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class GradeService {
  private apiUrl = `${environment.apiUrl}/api/grades`;

  constructor(private http: HttpClient) {}

  getStudentGrades(studentId: number): Observable<Grade[]> {
    return this.http.get<Grade[]>(`${this.apiUrl}/${studentId}`);
  }

  uploadGrades(file: File): Observable<any> {
    const formData = new FormData();
    formData.append('file', file);
    return this.http.post(`${environment.apiUrl}/api/upload`, formData);
  }

  generateTranscript(studentId: number): Observable<Blob> {
    return this.http.get(`${environment.apiUrl}/api/report/student/${studentId}`, {
      responseType: 'blob'
    });
  }
}