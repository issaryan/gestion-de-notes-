import { Component, OnInit } from '@angular/core';
import { UserService } from '../../../core/services/user.service';
import { GradeService } from '../../../core/services/grade.service';
import { ScheduleService, ScheduleEntry } from '../../../core/services/schedule.service';
import { User } from '../../../core/models/user.model';
import { Grade } from '../../../core/models/grade.model';
import { finalize, forkJoin } from 'rxjs';

@Component({
  selector: 'app-student-dashboard',
  templateUrl: './student-dashboard.component.html',
  styleUrls: ['./student-dashboard.component.scss']
})
export class StudentDashboardComponent implements OnInit {
  currentUser: User | null = null;
  grades: Grade[] = [];
  schedule: ScheduleEntry[] = [];
  loading = true;

  gradeChartData: any;
  gradeChartOptions: any;

  constructor(
    private userService: UserService,
    private gradeService: GradeService,
    private scheduleService: ScheduleService
  ) {
    this.initChartOptions();
  }

  ngOnInit(): void {
    this.loadDashboardData();
  }

  downloadTranscript(): void {
    if (!this.currentUser) return;

    this.gradeService.generateTranscript(this.currentUser.id)
      .subscribe(blob => {
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `releve_notes_${this.currentUser?.nom}_${this.currentUser?.prenom}.pdf`;
        link.click();
        window.URL.revokeObjectURL(url);
      });
  }

  private loadDashboardData(): void {
    this.loading = true;
    
    this.userService.getCurrentUser().subscribe(user => {
      this.currentUser = user;
      
      if (user) {
        forkJoin({
          grades: this.gradeService.getStudentGrades(user.id),
          schedule: this.scheduleService.getSchedule()
        })
        .pipe(finalize(() => this.loading = false))
        .subscribe({
          next: (data) => {
            this.grades = data.grades;
            this.schedule = data.schedule;
            this.updateChartData();
          },
          error: (error) => {
            console.error('Erreur lors du chargement des données:', error);
          }
        });
      }
    });
  }

  private initChartOptions(): void {
    this.gradeChartOptions = {
      plugins: {
        legend: {
          labels: {
            color: '#495057'
          }
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          max: 20,
          ticks: {
            stepSize: 5
          }
        }
      }
    };
  }

  private updateChartData(): void {
    const subjects = [...new Set(this.grades.map(g => g.subject))];
    const averages = subjects.map(subject => {
      const subjectGrades = this.grades.filter(g => g.subject === subject);
      return subjectGrades.reduce((sum, g) => sum + g.grade, 0) / subjectGrades.length;
    });

    this.gradeChartData = {
      labels: subjects,
      datasets: [{
        label: 'Moyenne par matière',
        data: averages,
        backgroundColor: 'rgba(54, 162, 235, 0.2)',
        borderColor: 'rgb(54, 162, 235)',
        borderWidth: 1
      }]
    };
  }
}