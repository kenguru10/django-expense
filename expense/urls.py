from django.urls import path, include
from . import views

urlpatterns = [
    path("", views.home_view, name="home"),
    path("auth/", views.auth_view, name="auth"),
    path("family/", views.family_view, name="family"),
    path("add/", views.add_view, name="add"),
    path("record/", views.records_view, name="record"),
    path("profile/", views.profile_view, name="profile"),
    # API endpoints
    path('logout/', views.logout_view, name='logout'),
    path("families/", views.family_collection_api, name="family_collection_api"),
    path(
        "families/<int:family_id>/", views.family_detail_api, name="family_detail_api"
    ),
    path(
        "families/<int:family_id>/members/",
        views.family_add_member_api,
        name="family_add_member_api",
    ),
    path(
        "families/<int:family_id>/members/<int:member_id>/",
        views.family_remove_member_api,
        name="family_remove_member_api",
    ),
    path("records/", views.record_collection_api, name="record_collection_api"),
    path('api/records/<int:record_id>/', views.record_detail_api, name='record_detail_api'),
    path("qrcodes/upload/", views.qrcode_upload_view, name="qrcode_upload"),
    path("qrcodes/<int:qrcode_id>/delete/", views.qrcode_delete_view, name="qrcode_delete"),
]
