from aquacore.i18n import LANGS

from .access import visible_fields
from .models import Alert


def shell(request):
    lang = request.session.get("lang", "en") if hasattr(request, "session") else "en"
    ctx = {"lang": lang, "langs": LANGS, "nav_fields": [], "unread_alerts": 0}
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        fields = visible_fields(request)
        ctx["nav_fields"] = fields
        ctx["unread_alerts"] = Alert.objects.filter(field__in=fields, is_read=False).count()
    return ctx
