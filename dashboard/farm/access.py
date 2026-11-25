from .models import Field


def visible_fields(request):
    """Staff (cooperative / admin) see every field; farmers see only their own."""
    qs = Field.objects.all().order_by("id")
    return qs if request.user.is_staff else qs.filter(owner_id=request.user.id)
