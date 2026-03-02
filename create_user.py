#!/usr/bin/env python
"""
Interactive script to create Django users with options to bypass email verification.
Run this script without arguments for interactive mode.
"""

import os
import sys
import django
from getpass import getpass

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netlog.settings')
django.setup()

from django.contrib.auth.models import User
from accounts.models import Profile

def print_header(text):
    """Print a formatted header"""
    print("\n" + "="*60)
    print(f" {text}")
    print("="*60)

def print_success(text):
    """Print success message"""
    print(f"✅ {text}")

def print_error(text):
    """Print error message"""
    print(f"❌ {text}")

def print_info(text):
    """Print info message"""
    print(f"📌 {text}")

def get_input(prompt, required=True, hidden=False):
    """Get user input with validation"""
    while True:
        if hidden:
            value = getpass(prompt)
        else:
            value = input(prompt).strip()
        
        if required and not value:
            print("❌ This field is required. Please try again.")
            continue
        return value

def get_yes_no(prompt, default='y'):
    """Get yes/no input from user"""
    valid = {'y': True, 'yes': True, 'n': False, 'no': False}
    if default == 'y':
        prompt = f"{prompt} [Y/n]: "
    else:
        prompt = f"{prompt} [y/N]: "
    
    while True:
        choice = input(prompt).strip().lower()
        if not choice:
            return valid[default]
        if choice in valid:
            return valid[choice]
        print("Please respond with 'y' or 'n'")

def create_user_interactive():
    """Interactive user creation"""
    print_header("CREATE NEW USER")
    
    # Get username
    while True:
        username = get_input("Enter username: ")
        if User.objects.filter(username=username).exists():
            print_error(f"Username '{username}' already exists. Please choose another.")
        else:
            break
    
    # Get email
    while True:
        email = get_input("Enter email address: ")
        if User.objects.filter(email=email).exists():
            print_error(f"Email '{email}' already exists. Please use another.")
        else:
            break
    
    # Get password
    while True:
        password = get_input("Enter password: ", hidden=True)
        if len(password) < 8:
            print_error("Password must be at least 8 characters long.")
            continue
        
        password_confirm = get_input("Confirm password: ", hidden=True)
        if password != password_confirm:
            print_error("Passwords don't match. Try again.")
        else:
            break
    
    # Get user type
    print_info("Select user type:")
    print("  1. Regular User")
    print("  2. Staff User")
    print("  3. Superuser (Admin)")
    
    user_type_choice = get_input("Enter choice [1/2/3] (default: 1): ", required=False)
    if not user_type_choice:
        user_type_choice = '1'
    
    is_superuser = (user_type_choice == '3')
    is_staff = (user_type_choice in ['2', '3'])
    
    user_type = "Superuser" if is_superuser else "Staff" if is_staff else "User"
    
    # Get organization (optional)
    organization = get_input("Enter organization (optional, press Enter to skip): ", required=False)
    
    # Email verification
    bypass_verification = get_yes_no("Bypass email verification?", default='y')
    
    print_header("USER SUMMARY")
    print(f"Username:     {username}")
    print(f"Email:        {email}")
    print(f"User Type:    {user_type}")
    if organization:
        print(f"Organization: {organization}")
    print(f"Verification: {'Bypassed' if bypass_verification else 'Required'}")
    
    if not get_yes_no("\nCreate this user?", default='y'):
        print_info("User creation cancelled.")
        return
    
    try:
        # Create user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            is_staff=is_staff,
            is_superuser=is_superuser
        )
        
        # Handle email verification
        if bypass_verification:
            user.is_active = True
            user.save()
            
            # Create or update profile
            profile, created = Profile.objects.get_or_create(user=user)
            profile.email_verified = True
            profile.email_verification_token = None
            profile.token_created_at = None
            if organization:
                profile.organization = organization
            profile.save()
            
            print_success(f"{user_type} '{username}' created with email already verified!")
        else:
            user.is_active = False
            user.save()
            
            profile, created = Profile.objects.get_or_create(user=user)
            profile.generate_verification_token()
            if organization:
                profile.organization = organization
            profile.save()
            
            print_success(f"User '{username}' created. Email verification required.")
            print_info(f"Verification token: {profile.email_verification_token}")
        
    except Exception as e:
        print_error(f"Error creating user: {e}")

def list_users_interactive():
    """List all users"""
    list_users()

def delete_user_interactive():
    """Interactive user deletion"""
    print_header("DELETE USER")
    
    # Show users first
    list_users()
    
    identifier = get_input("\nEnter username or ID of user to delete: ")
    
    try:
        if identifier.isdigit():
            user = User.objects.get(id=identifier)
        else:
            user = User.objects.get(username=identifier)
        
        print_header("USER TO DELETE")
        print(f"ID:       {user.id}")
        print(f"Username: {user.username}")
        print(f"Email:    {user.email}")
        print(f"Active:   {'Yes' if user.is_active else 'No'}")
        
        if get_yes_no(f"\nAre you sure you want to delete user '{user.username}'?", default='n'):
            user.delete()
            print_success(f"User '{user.username}' deleted successfully.")
        else:
            print_info("Deletion cancelled.")
            
    except User.DoesNotExist:
        print_error(f"User '{identifier}' not found.")

def update_password_interactive():
    """Interactive password update"""
    print_header("UPDATE USER PASSWORD")
    
    identifier = get_input("Enter username or ID of user: ")
    
    try:
        if identifier.isdigit():
            user = User.objects.get(id=identifier)
        else:
            user = User.objects.get(username=identifier)
        
        print_info(f"Updating password for user: {user.username}")
        
        while True:
            password = get_input("Enter new password: ", hidden=True)
            if len(password) < 8:
                print_error("Password must be at least 8 characters long.")
                continue
            
            password_confirm = get_input("Confirm new password: ", hidden=True)
            if password == password_confirm:
                user.set_password(password)
                user.save()
                print_success(f"Password updated successfully for user '{user.username}'.")
                break
            else:
                print_error("Passwords don't match. Try again.")
                
    except User.DoesNotExist:
        print_error(f"User '{identifier}' not found.")

def toggle_status_interactive():
    """Interactive user status toggle"""
    print_header("TOGGLE USER STATUS")
    
    identifier = get_input("Enter username or ID of user: ")
    
    try:
        if identifier.isdigit():
            user = User.objects.get(id=identifier)
        else:
            user = User.objects.get(username=identifier)
        
        current_status = "active" if user.is_active else "inactive"
        new_status = "inactive" if user.is_active else "active"
        
        print_info(f"User '{user.username}' is currently {current_status}.")
        
        if get_yes_no(f"Set user to {new_status}?", default='y'):
            user.is_active = not user.is_active
            user.save()
            print_success(f"User '{user.username}' is now {new_status}.")
        else:
            print_info("Status change cancelled.")
            
    except User.DoesNotExist:
        print_error(f"User '{identifier}' not found.")

def verify_email_interactive():
    """Interactive email verification"""
    print_header("VERIFY USER EMAIL")
    
    identifier = get_input("Enter username or ID of user: ")
    
    try:
        if identifier.isdigit():
            user = User.objects.get(id=identifier)
        else:
            user = User.objects.get(username=identifier)
        
        profile, created = Profile.objects.get_or_create(user=user)
        
        if profile.email_verified:
            print_info(f"User '{user.username}' already has verified email.")
            if not get_yes_no("Do you want to re-verify anyway?", default='n'):
                return
        
        profile.email_verified = True
        profile.email_verification_token = None
        profile.token_created_at = None
        profile.save()
        
        user.is_active = True
        user.save()
        
        print_success(f"Email verified for user '{user.username}'.")
        
    except User.DoesNotExist:
        print_error(f"User '{identifier}' not found.")

def list_users():
    """List all users with their status"""
    users = User.objects.all().select_related('profile')
    
    if not users:
        print_info("No users found.")
        return
    
    print_header("USER LIST")
    print(f"{'ID':<5} {'Username':<15} {'Email':<25} {'Type':<10} {'Active':<8} {'Verified':<10}")
    print("-" * 75)
    
    for user in users:
        user_type = "Superuser" if user.is_superuser else "Staff" if user.is_staff else "User"
        active = "✓" if user.is_active else "✗"
        
        try:
            verified = "✓" if user.profile.email_verified else "✗"
        except Profile.DoesNotExist:
            verified = "N/A"
        
        print(f"{user.id:<5} {user.username:<15} {user.email[:25]:<25} {user_type:<10} {active:<8} {verified:<10}")
    
    print("-" * 75)

def show_main_menu():
    """Display main menu and get user choice"""
    print_header("NETLOG USER MANAGEMENT")
    print("1. Create User")
    print("2. List Users")
    print("3. Delete User")
    print("4. Update Password")
    print("5. Toggle User Status")
    print("6. Verify Email")
    print("7. Exit")
    
    choice = get_input("Enter your choice [1-7]: ", required=False)
    return choice

def main():
    """Main interactive loop"""
    while True:
        choice = show_main_menu()
        
        if choice == '1':
            create_user_interactive()
        elif choice == '2':
            list_users()
        elif choice == '3':
            delete_user_interactive()
        elif choice == '4':
            update_password_interactive()
        elif choice == '5':
            toggle_status_interactive()
        elif choice == '6':
            verify_email_interactive()
        elif choice == '7' or choice == '':
            print_info("Goodbye!")
            sys.exit(0)
        else:
            print_error("Invalid choice. Please enter a number between 1 and 7.")
        
        input("\nPress Enter to continue...")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n📌 Goodbye!")
        sys.exit(0)