from http.client import REQUESTED_RANGE_NOT_SATISFIABLE
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.conf import settings
import random
import requests
from django.contrib import messages
from .models import *
from rest_framework.decorators import api_view
from django.http import HttpResponse, JsonResponse
import json
from .forms import SellYourCarForm
from django.contrib.auth import login
from .models import UserLogin
import urllib.parse
from django.contrib.auth.models import User
from django.views.decorators.cache import never_cache
from django.contrib import messages 


import requests
import json
import urllib.parse

def send_gupshup_otp(mobile, otp):
    api_url = "https://api.gupshup.io/wa/api/v1/template/msg"
    api_key = "uof28bqcclkmvxvvwniok63aptzuzsua"
    source = "918891348444"  # Your actual WhatsApp business number
    template_id = "aa7fc6f5-6811-4510-98d0-ab5d364cbf66"  # Your approved template's ID

    # Ensure correct mobile format
    if not mobile.startswith("91"):
        mobile = "91" + str(mobile)

    template_obj = {
        "id": template_id,
        "params": [str(otp)]  # Always a list, even for one variable
    }
    payload = {
        "source": source,
        "destination": mobile,
        "template": json.dumps(template_obj)
    }

    encoded_payload = urllib.parse.urlencode(payload)

    headers = {
        "apikey": api_key,
        "Content-Type": "application/x-www-form-urlencoded"
    }

    response = requests.post(api_url, headers=headers, data=encoded_payload)
    print(f"[Gupshup Response] {response.status_code} {response.text}")


# Email OTP sending - using Django’s built-in email
from django.core.mail import send_mail

def send_email_otp(email, otp):
    subject = "Your KAPS OTP"
    message = f"Welcome to KAPS! Your OTP is {otp}. This OTP is valid for a few minutes."
    send_mail(subject, message, 'noreply@kapscars.com', [email])
    print(f"[DEV] Email OTP sent to {email}")

def user_login(request):
    if request.method == 'POST':
        name = request.POST['name']
        email = request.POST['email']
        mobile = request.POST['mobile']

        otp = random.randint(1000, 9999)
        print(f"Generated OTP: {otp} for mobile: {mobile}")

        request.session['user_data'] = {
            'name': name,
            'email': email,
            'mobile': mobile,
            'otp': otp
        }

        # WhatsApp OTP sending 
        try:
            send_gupshup_otp(mobile, otp)
        except Exception as e:
            print("WhatsApp OTP send failed:", e)
            messages.warning(request, "WhatsApp OTP could not be sent. Please use Email OTP.")

        # Email OTP sending 
        try:
            send_email_otp(email, otp)
        except Exception as e:
            print("Email OTP send failed:", e)
            messages.error(request, "Email OTP could not be sent. Please try again later.")

        if not UserLogin.objects.filter(email=email).exists():
            user_obj = UserLogin(name=name, email=email, mobile=mobile)
            user_obj.save()

        return redirect('otp')

    if 'is_logged_in' in request.session and request.session['is_logged_in']:
        return redirect('collections')

    return render(request, 'login.html')




from django.urls import reverse
@never_cache
def otp_verification(request):
    if request.method == 'POST':
        otp_1 = request.POST.get('otp_1')
        otp_2 = request.POST.get('otp_2')
        otp_3 = request.POST.get('otp_3')
        otp_4 = request.POST.get('otp_4')
        entered_otp = otp_1 + otp_2 + otp_3 + otp_4

        user_data = request.session.get('user_data')
        if not user_data:
            return HttpResponse("Session expired. Please login again.")

        stored_otp = str(user_data.get('otp'))
        print(f"Entered OTP: {entered_otp}, Stored OTP: {stored_otp}")

        if entered_otp == stored_otp:
            user, created = User.objects.get_or_create(
                username=user_data['email'],
                defaults={'email': user_data['email'], 'first_name': user_data['name'], 'last_name': ''},
            )

            user_obj = UserLogin.objects.get(email=user_data['email'])
            user_obj.is_active = True
            user_obj.save()
            request.session['is_logged_in'] = True
            login(request, user)

            # Debug statements to check session keys
            sell_car_key = request.session.get('sell_car_key')
            find_car_key = request.session.get('find_car_key')
            car_details_key = request.session.get('car_details_key')
            futured_car_key = request.session.get('car_details_key')



            if sell_car_key:
                del request.session['sell_car_key']
                return redirect(sell_car_key)

            if find_car_key:
                del request.session['find_car_key']
                return redirect(find_car_key)

            if car_details_key:
                del request.session['car_details_key']
                return redirect(car_details_key)

            if futured_car_key:
                del request.session['futured_car_key']
                return redirect(futured_car_key)

            return redirect('home')
        else:
            messages.error(request, 'Invalid OTP. Please try again.')

    return render(request, 'otp.html')



def resend_otp(request):
    user_data = request.session.get('user_data')
    if not user_data:
        return JsonResponse({'status': 'error', 'message': 'Session expired. Please login again.'})

    mobile = user_data.get('mobile')
    otp = random.randint(1000, 9999)

    # Update the OTP and reassign the user_data dict to ensure session is updated
    user_data['otp'] = otp
    request.session['user_data'] = user_data  # Key step: reassign!
    request.session.modified = True  # Ensures Django persists the change

    print(f"Regenerated OTP: {otp} for mobile: {mobile}")

    try:
        send_gupshup_otp(mobile, otp)
    except Exception as e:
        print("WhatsApp OTP resend failed:", e)

    try:
        send_email_otp(user_data.get('email'), otp)
    except Exception as e:
        print("Email OTP resend failed:", e)

    return JsonResponse({'status': 'success', 'message': 'OTP has been resent successfully.'})



# logout
def logout(request):
    request.session.flush()
    return redirect('login')


# landing page
def home(request):
    futured_cars = Cars.objects.all()
    return render(request, 'index.html', {'futured_cars':futured_cars})



def futured_cars(request, id):
    if request.user.is_authenticated:
        cars = Cars.objects.get(id=int(id))
        return render(request, 'car_details.html', {'cars':cars})
    else:
        request.session['car_details_key'] = request.path
        return redirect('login')



# find Your Car Form Submission
def find_a_car(request):
    if request.user.is_authenticated:
        fuel_choices = Fuel_type.objects.all().distinct()
        transmission_types = Transmission.objects.all().distinct()
        if request.method == 'POST':
            budget = request.POST.get('budget')
            fuel_type = request.POST.get('fuel')
            transmission = request.POST.get('transmission')

            budget_ranges = {
                '0-10': (0, 1000000),
                '10-20': (1000000, 2000000),
                '20-30': (2000000, 3000000),
                '30+': (3000000, float('inf'))
            }

            if budget != '30+':
                if budget in budget_ranges:
                    budget_min, budget_max = budget_ranges[budget]
                    filtered_cars = Cars.objects.filter(
                        fuel__Available_fuel_type=fuel_type,
                        transmission__Transmission_type=transmission,
                        price__gte=budget_min,
                        price__lte=budget_max if budget != '30+' else budget_min
                    )
                else:
                    filtered_cars = Cars.objects.none()
            else:
                filtered_cars = Cars.objects.filter(
                    fuel__Available_fuel_type=fuel_type,
                    transmission__Transmission_type=transmission,
                    price__gte=3000000,
                )

            return render(request, 'collections.html', {'cars':filtered_cars})

        context = {
            'fuel_choices': fuel_choices,
            'transmission_types': transmission_types
        }

        return render(request, 'find_car.html', context)
    else:
        request.session['find_car_key'] = 'find_a_car'

        return redirect('login')



from django.db.models import Q
# car collections
def collections(request):
    car_brand = Brand.objects.all().distinct()
    transmission_types = Transmission.objects.all().distinct()
    years = Cars.objects.values_list('reg_year', flat=True).distinct()
    data_set = Cars.objects.none()  # Initialize an empty queryset

    if request.method == 'POST':
        budget = request.POST.get('budget')
        year = request.POST.getlist('year')
        brand = request.POST.getlist('brand')
        transmission = request.POST.getlist('transmission')

        request.session['budget'] = budget
        if not budget:
            request.session['year'] = year
            request.session['brand'] = brand
            request.session['transmission'] = transmission

        budget = request.session.get('budget')
        year = request.session.get('year')
        brand = request.session.get('brand')
        transmission = request.session.get('transmission')

        budget_ranges = {
            '0-10': (0, 1000000),
            '10-20': (1000000, 2000000),
            '20-30': (2000000, 3000000),
            '30+': (3000000, float('inf'))
        }

        # Apply budget filter
        if budget and budget!='30+' and budget in budget_ranges:
            budget_min, budget_max = budget_ranges[budget]
            data_set = Cars.objects.filter(price__gte=budget_min, price__lte=budget_max)
        elif budget == '30+':
            data_set = Cars.objects.filter(price__gte=3000000)
        else:
            data_set = Cars.objects.all()  # No budget filter applied

        # Apply year filter
        if year:
            data_set = data_set.filter(reg_year__in=year)

        # Apply brand filter
        if brand:
            data_set = data_set.filter(brand__Available_brands__in=brand)

        # Apply transmission filter
        if transmission:
            data_set = data_set.filter(transmission__Transmission_type__in=transmission)

    else:
        data_set = Cars.objects.filter(is_listed=True)

    print(list(data_set))
    context = {
        'cars': list(data_set),
        'car_brand': car_brand,
        'transmission_types': transmission_types,
        'years': years
    }
    return render(request, 'collections.html', context)




# Sell Your Car
def sell_a_car(request):
    if request.user.is_authenticated:
        if request.method == 'POST':
            car_reg_number = request.POST.get('car_reg_number')
            car_brand = request.POST.get('car_brand')
            car_model = request.POST.get('car_model')
            registered_year = request.POST.get('registered_year')
            fuel_type = request.POST.get('fuel_type')
            km_driven = request.POST.get('km_driven')
            selling_price = request.POST.get('selling_price')
            images = request.FILES.get('images')

            brand = Brand.objects.get(Available_brands=car_brand)
            fuel = Fuel_type.objects.get(Available_fuel_type=fuel_type)
            user_obj = UserLogin.objects.get(email = request.user.email)
            sell=SellYourCar(
                car_reg_number=car_reg_number,
                brand_name=brand,
                car_model=car_model,
                registered_year=registered_year,
                fuel_type=fuel,
                km_driven=km_driven,
                selling_price=selling_price,
                images=images,
                proposed_user = user_obj,
                proposed_staff = None
            )

            sell.save()

            return redirect('proposal_success')

        car_brands = Brand.objects.all().distinct()
        car_fuel_types = Fuel_type.objects.all().distinct()

        context = {
            'car_brands': car_brands,
            'car_fuel_types': car_fuel_types,
        }
        return render(request, 'sell_a_car.html', context)
    else:
        request.session['sell_car_key'] = 'sell_a_car'
        return redirect('login')



# # Proposal Success
def proposal_success(request):
    return render(request, 'proposal_success.html')



# Happiness Club
def happiness_club_view(request):
    happiness_club_members = HappinessClub.objects.all()
    return render(request, 'happiness_club.html', {'happiness_club_members': happiness_club_members})




# Careers Page
def careers(request):
    careers = Career.objects.all()
    return render(request, 'careers.html', {'careers': careers})



#kaps assured
def kaps_assured(request):
    return render(request, 'kaps_assured.html')



#about us
def about_us(request):
    return render(request, 'about_us.html')


#car details
def car_details(request, id):
    if request.user.is_authenticated:
        cars = Cars.objects.get(id=int(id))
        image_list = Car_Image.objects.filter(car__id=cars.id).all()
        car_price = cars.price
        similar_cars = Cars.objects.filter(price__gte=car_price)

        context={
            'cars':cars,
            'car_images':image_list,
            'similar_cars':similar_cars,
            }
        return render(request, 'car_details.html', context)
    else:
        request.session['car_details_key'] = request.path
        return redirect('login')


#emi
def emi(request):
    return render(request, 'emi.html')


from urllib.parse import urlencode
def filter(request):
    brands = Brand.objects.all().distinct()
    transmissions = Transmission.objects.all().distinct()
    years = Cars.objects.values_list('reg_year', flat=True).distinct()

    return render(request, 'filter_page.html', {
        'brands': brands,
        'transmission_types': transmissions,
        'years': sorted(years, reverse=True),
    })



# from django.urls import reverse
@login_required
def test_drive(request,id):
    cars = Cars.objects.get(id=id)
    user_obj, created = UserLogin.objects.get_or_create(
        email=request.user.email,
        defaults={
            'name': request.user.get_full_name() or request.user.username,
            'mobile': ''
        }
    )

    if not Test_drive.objects.filter(car_data=cars,user_data =user_obj).exists():
        test_drive_obj = Test_drive(user_data=user_obj,car_data=cars)
        test_drive_obj.save()
    else:
        messages.error(request, 'You have already given submission for Test drive.')

        return redirect(f'../car_details/{id}/')
    return render(request, 'proposal_success.html')




@login_required
def book_now(request,id):
    cars = Cars.objects.get(id=id)
    user_obj, created = UserLogin.objects.get_or_create(
        email=request.user.email,
        defaults={
            'name': request.user.get_full_name() or request.user.username,
            'mobile': ''
        }
    )

    if not Book_now.objects.filter(car_data=cars,user_data =user_obj).exists():
        test_drive_obj = Book_now(user_data=user_obj,car_data=cars)
        test_drive_obj.save()
    else:
        messages.error(request, 'You have already given submission for Booking.')

        return redirect(f'../car_details/{id}/')

    return render(request, 'proposal_success.html')




def privacy_policy(request):
    return render(request, 'privacy_policy.html')



def terms_and_conditions(request):
    return render(request, 'terms.html')

from django.shortcuts import redirect

def emi_redirect(request):
    return redirect('emi_calculator', permanent=True)
