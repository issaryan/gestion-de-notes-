import { Component, OnInit } from '@angular/core';
import { UserService } from '../../../core/services/user.service';
import { ClassService } from '../../../core/services/class.service';
import { User } from '../../../core/models/user.model';
import { Class } from '../../../core/models/class.model';
import { finalize } from 'rxjs';

@Component({
  selector: 'app-admin-dashboard',
  templateUrl: './admin-dashboard.component.html',
  styleUrls: ['./admin-dashboard.component.scss']
})
export class AdminDashboardComponent implements OnInit {
  recentUsers: User[] = [];
  classes: Class[] = [];
  loading = true;
  userStats = {
    total: 0,
    active: 0,
    teachers: 0,
    students: 0
  };

  constructor(
    private userService: UserService,
    private classService: ClassService
  ) {}

  ngOnInit(): void {
    this.loadDashboardData();
  }

  private loadDashboardData(): void {
    this.loading = true;
    
    this.userService.getUsers()
      .pipe(finalize(() => this.loading = false))
      .subscribe(users => {
        this.recentUsers = users.slice(0, 5);
        this.userStats = {
          total: users.length,
          active: users.filter(u => u.status === 'Actif').length,
          teachers: users.filter(u => u.role === 'teacher').length,
          students: users.filter(u => u.role === 'student').length
        };
      });
  }
}