from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .forms import RegisterForm
from django.contrib.auth.decorators import login_not_required
from django.contrib import messages

def register_view(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Welcome, {user.username}! Your account has been created successfully.")
            messages.info(request, "You have been automatically logged in.")
            return redirect("dashboard")
        else:
            # Show form errors as messages
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.capitalize()}: {error}")
    else:
        form = RegisterForm()

    return render(request, "accounts/register.html", {"form": form})


@login_not_required
def login_view(request):
    if request.method == "POST":
        username_or_email = request.POST.get("username")
        password = request.POST.get("password")

        # Check if fields are empty
        if not username_or_email or not password:
            messages.warning(request, "Please enter both username and password.")
            return render(request, "accounts/login.html")

        user = authenticate(request, username=username_or_email, password=password)

        if user is not None:
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            
            # Check if user is a superuser
            if user.is_superuser:
                messages.info(request, "Redirecting to admin panel...")
                return redirect("admin:index")  # Redirect to Django admin
            else:
                messages.info(request, "Redirecting to dashboard...")
                return redirect("dashboard")  # Redirect regular users to dashboard
        else:
            messages.error(request, "Invalid username or password. Please try again.")
            return render(request, "accounts/login.html")

    return render(request, "accounts/login.html")


def logout_view(request):
    username = request.user.username if request.user.is_authenticated else "Guest"
    logout(request)
    messages.success(request, f"You have been logged out successfully. Goodbye, {username}!")
    messages.info(request, "Hope to see you again soon!")
    return redirect("login")




@login_required
def dashboard_view(request):
    # Check if user is a superuser and redirect to admin panel
    if request.user.is_superuser:
        messages.info(request, "Redirecting to admin panel...")
        return redirect("admin:index")
    
    # Regular users see the dashboard
    return render(request, "accounts/dashboard.html")
