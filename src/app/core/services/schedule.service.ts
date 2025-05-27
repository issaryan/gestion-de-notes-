import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface ScheduleEntry {
  subject_id: number;
  day: 'MON' | 'TUE' | 'WED' | 'THU' | 'FRI' | 'SAT';
  start_time: string;
  end_time: string;
  subject_name?: string;
  class_name?: string;
}

@Injectable({
  providedIn: 'root'
})
export class ScheduleService {
  private apiUrl = `${environment.apiUrl}/api/schedule`;

  constructor(private http: HttpClient) {}

  getSchedule(): Observable<ScheduleEntry[]> {
    return this.http.get<ScheduleEntry[]>(this.apiUrl);
  }

  updateSchedule(schedule: ScheduleEntry[]): Observable<void> {
    return this.http.put<void>(this.apiUrl, schedule);
  }
}