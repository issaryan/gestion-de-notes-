import { Injectable } from '@angular/core';
import { CanActivate, Router, ActivatedRouteSnapshot, RouterStateSnapshot } from '@angular/router';
import { AuthService } from '../services/auth.service';

@Injectable({
  providedIn: 'root'
})
export class AuthGuard implements CanActivate {
  constructor(
    private authService: AuthService,
    private router: Router
  ) {}

  canActivate(route: ActivatedRouteSnapshot, state: RouterStateSnapshot): boolean {
    if (this.authService.isAuthenticated()) {
      const user = this.authService.getCurrentUser();
      const requiredRoles = route.data['roles'] as string[];

      if (!requiredRoles || !user) {
        return true;
      }

      if (requiredRoles.includes(user.role)) {
        return true;
      }

      this.router.navigate(['/unauthorized']);
      return false;
    }

    this.router.navigate(['/login'], { queryParams: { returnUrl: state.url }});
    return false;
  }
}