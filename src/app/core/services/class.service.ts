import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { Class } from '../models/class.model';
import { environment } from '../../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class ClassService {
  private apiUrl = `${environment.apiUrl}/api/classes`;

  constructor(private http: HttpClient) {}

  getClass(id: number): Observable<Class> {
    return this.http.get<Class>(`${this.apiUrl}/${id}`);
  }

  generateReport(classId: number, type: 'summary' | 'detailed' = 'summary'): Observable<Blob> {
    return this.http.get(`${this.apiUrl}/${classId}/report?type=${type}`, {
      responseType: 'blob'
    });
  }
}