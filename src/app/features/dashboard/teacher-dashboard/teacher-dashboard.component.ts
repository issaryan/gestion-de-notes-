import { Component, OnInit } from '@angular/core';
import { UserService } from '../../../core/services/user.service';
import { ScheduleService, ScheduleEntry } from '../../../core/services/schedule.service';
import { User } from '../../../core/models/user.model';
import { finalize, forkJoin } from 'rxjs';

@Component({
  selector: 'app-teacher-dashboard',
  templateUrl: './teacher-dashboard.component.html',
  styleUrls: ['./teacher-dashboard.component.scss']
})
export class TeacherDashboardComponent implements OnInit {
  students: User[] = [];
  schedule: ScheduleEntry[] = [];
  loading = true;
  currentUser: User | null = null;

  constructor(
    private userService: UserService,
    private scheduleService: ScheduleService
  ) {}

  ngOnInit(): void {
    this.loadDashboardData();
  }

  private loadDashboardData(): void {
    this.loading = true;
    
    forkJoin({
      currentUser: this.userService.getCurrentUser(),
      students: this.userService.getUsers(),
      schedule: this.scheduleService.getSchedule()
    })
    .pipe(finalize(() => this.loading = false))
    .subscribe({
      next: (data) => {
        this.currentUser = data.currentUser;
        this.students = data.students;
        this.schedule = data.schedule;
      },
      error: (error) => {
        console.error('Erreur lors du chargement des données:', error);
      }
    });
  }
}