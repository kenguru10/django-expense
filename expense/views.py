from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.urls import reverse_lazy
from django.contrib import messages

# Create your views here.
@login_required(login_url=reverse_lazy('auth'))
def home_view(request):
    return render(request, 'expense/home.html')

def auth_view(request):
    tab = 'login'
    if request.method == 'POST':
        if 'login' in request.POST:
            tab = 'login'
            username = request.POST.get('username')
            password = request.POST.get('password')
            print(username, password)
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('home')
            else:
                messages.error(request, 'Invalid username or password.')
        elif 'register' in request.POST:
            tab = 'register'
            name = request.POST.get('name')
            email = request.POST.get('email')
            password = request.POST.get('password')
            confirm = request.POST.get('confirm')
            if password != confirm:
                messages.error(request, 'Passwords do not match.')
            elif User.objects.filter(username=email).exists():
                messages.error(request, 'Email already registered.')
            else:
                user = User.objects.create_user(username=email, email=email, password=password, first_name=name)
                login(request, user)
                return redirect('home')
    return render(request, 'auths/auths.html', {'tab': tab})

def family_view(request):
    return render(request, 'expense/family.html')