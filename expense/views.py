from datetime import datetime, timedelta
import uuid
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.urls import reverse_lazy
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse, HttpResponseBadRequest
import json

from .models import Account, Family, Record, QRCode


def _serialize_member(user):
    try:
        return {
            "name": f"{getattr(user, 'first_name', '')}".strip()
            or (getattr(user, "username", None) or getattr(user, "email", None)),
            "email": getattr(user, "email", None) or getattr(user, "username", None),
        }
    except Exception as e:
        return {"error": f"Failed to serialize member: {str(e)}"}


def _serialize_family(family: Family):
    try:
        return {
            "id": getattr(family, "id", None),
            "pid": getattr(family, "pid", None),
            "name": getattr(family, "name", None),
            "level": getattr(family, "level", None),
            "max_budget": getattr(family, "max_budget", None),
            "currency": getattr(family, "currency", None),
            "members": (
                [_serialize_member(u) for u in getattr(family, "members", []).all()]
                if hasattr(getattr(family, "members", None), "all")
                else []
            ),
        }
    except Exception as e:
        return {"error": f"Failed to serialize family: {str(e)}"}


def _serialize_account(account: Account):
    try:
        return {
            "pid": getattr(account, "pid", None),
            "user": _serialize_member(getattr(account, "user", None)),
            "expired_at": getattr(account, "expired_at", None),
            "created_at": getattr(account, "created_at", None),
            "updated_at": getattr(account, "updated_at", None),
        }
    except Exception as e:
        return {"error": f"Failed to serialize account: {str(e)}"}


def _serialize_record(record: Record):
    try:
        return {
            "id": getattr(record, "id", None),  # <-- Add this line
            "pid": getattr(record, "pid", None),
            "family": _serialize_family(getattr(record, "family", None)),
            "name": getattr(record, "name", None),
            "amount": getattr(record, "amount", None),
            "category": getattr(record, "category", None),
            "description": getattr(record, "description", None),
            "who": _serialize_member(getattr(record, "who", None)),
            "created_at": getattr(record, "created_at", None),
        }
    except Exception as e:
        return {"error": f"Failed to serialize record: {str(e)}"}


def get_or_create_account(user: User) -> Account:
    account = Account.objects.filter(user=user).first()

    with transaction.atomic():
        if not account:
            account = Account.objects.create(
                user=user, expired_at=datetime.now() + timedelta(days=365)
            )
        account.refresh_from_db()

    return account


# Create your views here.
@login_required(login_url=reverse_lazy("auth"))
def home_view(request):
    account = get_or_create_account(user=request.user)
    try:
        family = Family.objects.prefetch_related("members").get(members=request.user)
    except Family.DoesNotExist:
        family = None

    summary = {
        "total_amount_this_month": 0,
    }
    records = Record.objects.filter(
        family=family, created_at__month=datetime.now().month
    )
    for record in records:
        summary["total_amount_this_month"] += record.amount

    # QR codes for this family
    if family is not None:
        qrcodes = QRCode.objects.filter(family=family).order_by("-created_at")
    else:
        qrcodes = []

    # Aggregate spending per member
    member_spending = (
        Record.objects.filter(family=family, created_at__month=datetime.now().month)
        .values("who__first_name", "who__username", "who__email")
        .annotate(total=Sum("amount"))
    )
    # Prepare for chart: labels and data
    chart_labels = []
    chart_data = []
    for m in member_spending:
        name = m["who__first_name"] or m["who__username"] or m["who__email"]
        chart_labels.append(name)
        chart_data.append(m["total"] or 0)

    return render(
        request,
        "expense/home.html",
        {
            "family": _serialize_family(family),
            "account": _serialize_account(account),
            "summary": summary,
            "chart_labels": chart_labels,
            "chart_data": chart_data,
            "qrcodes": qrcodes,
        },
    )


def auth_view(request):
    tab = "login"
    if request.method == "POST":
        if "login" in request.POST:
            tab = "login"
            username = request.POST.get("username")
            password = request.POST.get("password")
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect("home")
            else:
                messages.error(request, "Invalid username or password.")
        elif "register" in request.POST:
            tab = "register"
            full_name = request.POST.get("full_name")
            username = request.POST.get("username")
            email = request.POST.get("email")
            password = request.POST.get("password")
            confirm = request.POST.get("confirm")
            if password != confirm:
                messages.error(request, "Passwords do not match.")
            elif User.objects.filter(username=email).exists():
                messages.error(request, "Email already registered.")
            else:
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=full_name,
                )
                login(request, user)
                return redirect("home")
    return render(request, "auths/auths.html", {"tab": tab})


def family_view(request):
    return render(request, "expense/family.html")


def add_view(request):
    return render(request, "expense/add.html")


def records_view(request):
    return render(request, "expense/records.html")


def profile_view(request):
    return render(request, "expense/profile.html")


@login_required(login_url=reverse_lazy("auth"))
@require_http_methods(["POST"])
def qrcode_upload_view(request):
    """Upload one or more QR code images for the current user's family."""
    try:
        family = Family.objects.prefetch_related("members").get(members=request.user)
    except Family.DoesNotExist:
        messages.error(request, "Create or join a family before uploading QR codes.")
        return redirect("home")

    files = request.FILES.getlist("qrcodes")
    if not files:
        messages.error(request, "Please select at least one image to upload.")
        return redirect("home")

    created_any = False
    for file in files:
        if getattr(file, "content_type", "").startswith("image/"):
            QRCode.objects.create(family=family, image=file)
            created_any = True

    if created_any:
        messages.success(request, "QR codes uploaded successfully.")
    else:
        messages.error(request, "No valid image files were uploaded.")

    return redirect("home")


def logout_view(request):
    logout(request)
    return redirect("auth")


# API endpoints


@login_required(login_url=reverse_lazy("auth"))
@require_http_methods(["GET", "POST"])
def family_collection_api(request):
    # GET: list families current user belongs to
    if request.method == "GET":
        families = (
            Family.objects.filter(members=request.user)
            .prefetch_related("members")
            .order_by("-created_at")
        )
        data = [_serialize_family(f) for f in families]
        return JsonResponse({"families": data}, status=200)

    # POST: create a new family; current user auto-joined as a member
    # Accept JSON or form-encoded
    try:
        if request.content_type and "application/json" in request.content_type:
            payload = json.loads(request.body or "{}")
        else:
            payload = request.POST
        name = (payload.get("name") or "").strip()
        level = int(payload.get("level") or 1)
        max_budget = float(payload.get("max_budget") or 0)
        currency = (payload.get("currency") or "HKD").strip() or "HKD"
    except (ValueError, json.JSONDecodeError):
        return HttpResponseBadRequest("Invalid request payload.")

    if not name:
        return HttpResponseBadRequest("Field 'name' is required.")

    with transaction.atomic():
        family = Family.objects.create(
            name=name,
            level=level,
            max_budget=max_budget,
            currency=currency,
        )
        family.members.add(request.user)

    return JsonResponse(_serialize_family(family), status=201)


@login_required(login_url=reverse_lazy("auth"))
@require_http_methods(["GET", "POST", "PUT"])
def family_detail_api(request, family_id: int):
    try:
        family = Family.objects.prefetch_related("members").get(
            id=family_id, members=request.user
        )
    except Family.DoesNotExist:
        return JsonResponse(
            {"detail": "Family not found or access denied."}, status=404
        )

    if request.method == "GET":
        return JsonResponse(_serialize_family(family), status=200)

    # POST/PUT: update allowed fields
    try:
        if request.content_type and "application/json" in request.content_type:
            payload = json.loads(request.body or "{}")
        else:
            payload = request.POST
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON payload.")

    name = payload.get("name", None)
    level = payload.get("level", None)
    max_budget = payload.get("max_budget", None)
    currency = payload.get("currency", None)

    changed = False
    if name is not None:
        name = name.strip()
        if not name:
            return HttpResponseBadRequest("Field 'name' cannot be empty.")
        family.name = name
        changed = True
    if level is not None:
        try:
            family.level = int(level)
            changed = True
        except ValueError:
            return HttpResponseBadRequest("Field 'level' must be an integer.")
    if max_budget is not None:
        try:
            family.max_budget = float(max_budget)
            changed = True
        except ValueError:
            return HttpResponseBadRequest("Field 'max_budget' must be a number.")
    if currency is not None:
        currency = currency.strip()
        if not currency:
            return HttpResponseBadRequest("Field 'currency' cannot be empty.")
        family.currency = currency
        changed = True

    if changed:
        family.save()

    return JsonResponse(_serialize_family(family), status=200)


@login_required(login_url=reverse_lazy("auth"))
@require_http_methods(["POST"])
def family_add_member_api(request, family_id: int):
    # Body: { "email": "user@example.com" }
    try:
        if request.content_type and "application/json" in request.content_type:
            payload = json.loads(request.body or "{}")
        else:
            payload = request.POST
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON payload.")

    email = (payload.get("email") or "").strip()
    if not email:
        return HttpResponseBadRequest("Field 'email' is required.")

    try:
        family = Family.objects.prefetch_related("members").get(
            id=family_id, members=request.user
        )
    except Family.DoesNotExist:
        return JsonResponse(
            {"detail": "Family not found or access denied."}, status=404
        )

    try:
        target_user = User.objects.get(email=email)  # only existing users can be added
    except User.DoesNotExist:
        return JsonResponse(
            {"detail": "User with this email does not exist."}, status=404
        )

    ok, err = family.add_member(target_user)
    if not ok:
        return JsonResponse({"detail": err}, status=400)

    family.refresh_from_db()
    return JsonResponse(_serialize_family(family), status=201)


@login_required(login_url=reverse_lazy("auth"))
@require_http_methods(["POST", "DELETE"])
def family_remove_member_api(request, family_id: int, member_id: int):
    try:
        family = Family.objects.prefetch_related("members").get(
            id=family_id, members=request.user
        )
    except Family.DoesNotExist:
        return JsonResponse(
            {"detail": "Family not found or access denied."}, status=404
        )

    try:
        target_user = User.objects.get(id=member_id)
    except User.DoesNotExist:
        return JsonResponse({"detail": "User not found."}, status=404)

    ok, err = family.remove_member(target_user)
    if not ok:
        return JsonResponse({"detail": err}, status=400)

    family.refresh_from_db()
    return JsonResponse(_serialize_family(family), status=200)


@login_required(login_url=reverse_lazy("auth"))
@require_http_methods(["GET", "POST"])
def record_collection_api(request):
    # Body: { "family_id": family_id, "amount": amount, "category": category, "description": description, "created_at": created_at }

    if request.method == "GET":
        records = (
            Record.objects.filter(family__members=request.user)
            .select_related("family")
            .order_by("-created_at")
        )
        data = [_serialize_record(r) for r in records]
        return JsonResponse({"records": data}, status=200)

    try:
        if request.content_type and "application/json" in request.content_type:
            payload = json.loads(request.body or "{}")
        else:
            payload = request.POST
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON payload.")

    # Handle PUT for updating a record
    if request.method == "PUT":
        record_id = None
        # Try to get record id from URL (if using Django REST, you may have kwargs)
        # Here, try to get from payload
        record_id = payload.get("id")
        record_pid = payload.get("pid")
        record = None
        if record_id:
            record = Record.objects.filter(
                id=record_id, family__members=request.user
            ).first()
        elif record_pid:
            record = Record.objects.filter(
                pid=record_pid, family__members=request.user
            ).first()
        if not record:
            return JsonResponse(
                {"detail": "Record not found or access denied."}, status=404
            )

        name = payload.get("name", None)
        amount = payload.get("amount", None)
        category = payload.get("category", None)
        description = payload.get("description", None)
        created_at = payload.get("created_at", None)

        changed = False
        if name is not None:
            record.name = name
            changed = True
        if amount is not None:
            try:
                record.amount = float(amount)
                changed = True
            except ValueError:
                return HttpResponseBadRequest("Field 'amount' must be a number.")
        if category is not None:
            record.category = category
            changed = True
        if description is not None:
            record.description = description
            changed = True
        if created_at is not None:
            # Expecting format 'YYYY-MM-DDTHH:MM' or ISO string
            try:
                from django.utils.dateparse import parse_datetime

                dt = parse_datetime(created_at)
                if not dt:
                    # Try without seconds
                    import datetime as dtmod

                    try:
                        dt = dtmod.datetime.strptime(created_at, "%Y-%m-%dT%H:%M")
                    except Exception:
                        return HttpResponseBadRequest(
                            "Field 'created_at' format invalid."
                        )
                record.created_at = dt
                changed = True
            except Exception:
                return HttpResponseBadRequest("Field 'created_at' format invalid.")

        if changed:
            record.save()
        return JsonResponse(_serialize_record(record), status=200)

    # POST: create new record
    family_id = payload.get("family_id", None)
    name = payload.get("name", None)
    amount = payload.get("amount", None)
    category = payload.get("category", None)
    description = payload.get("description", None)
    created_at = payload.get("created_at", None)

    if not family_id:
        return HttpResponseBadRequest("Field 'family_id' is required.")
    if not name:
        return HttpResponseBadRequest("Field 'name' is required.")
    if not amount:
        return HttpResponseBadRequest("Field 'amount' is required.")
    if not category:
        return HttpResponseBadRequest("Field 'category' is required.")

    try:
        with transaction.atomic():
            record = Record(
                family=Family.objects.get(id=family_id),
                name=name,
                amount=amount,
                category=category,
                description=description,
                who=request.user,
            )
            if created_at:
                from django.utils.dateparse import parse_datetime

                dt = parse_datetime(created_at)
                if not dt:
                    import datetime as dtmod

                    try:
                        dt = dtmod.datetime.strptime(created_at, "%Y-%m-%dT%H:%M")
                    except Exception:
                        return HttpResponseBadRequest(
                            "Field 'created_at' format invalid."
                        )
                record.created_at = dt
            record.save()
        return JsonResponse(_serialize_record(record), status=201)
    except Exception as e:
        return JsonResponse({"detail": str(e)}, status=400)



@login_required(login_url=reverse_lazy("auth"))
@require_http_methods(["GET", "PUT", "DELETE"])
def record_detail_api(request, record_id: int):
    try:
        record = Record.objects.select_related("family").get(
            id=record_id, family__members=request.user
        )
    except Record.DoesNotExist:
        return JsonResponse(
            {"detail": "Record not found or access denied."}, status=404
        )

    if request.method == "GET":
        return JsonResponse(_serialize_record(record), status=200)

    if request.method == "PUT":
        try:
            if request.content_type and "application/json" in request.content_type:
                payload = json.loads(request.body or "{}")
            else:
                payload = request.POST
        except json.JSONDecodeError:
            return HttpResponseBadRequest("Invalid JSON payload.")

        name = payload.get("name", None)
        amount = payload.get("amount", None)
        category = payload.get("category", None)
        description = payload.get("description", None)
        created_at = payload.get("created_at", None)

        changed = False
        if name is not None:
            record.name = name
            changed = True
        if amount is not None:
            try:
                record.amount = float(amount)
                changed = True
            except ValueError:
                return HttpResponseBadRequest("Field 'amount' must be a number.")
        if category is not None:
            record.category = category
            changed = True
        if description is not None:
            record.description = description
            changed = True
        if created_at is not None:
            from django.utils.dateparse import parse_datetime

            dt = parse_datetime(created_at)
            if not dt:
                import datetime as dtmod

                try:
                    dt = dtmod.datetime.strptime(created_at, "%Y-%m-%dT%H:%M")
                except Exception:
                    return HttpResponseBadRequest("Field 'created_at' format invalid.")
            record.created_at = dt
            changed = True

        if changed:
            record.save()
        return JsonResponse(_serialize_record(record), status=200)

    if request.method == "DELETE":
        record.delete()
        return JsonResponse({"detail": "Record deleted."}, status=204)
