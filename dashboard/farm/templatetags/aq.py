from aquacore.i18n import ui
from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def t(context, key, **kwargs):
    """{% t "key" %} or {% t "key" p=value %}: translated UI text for the session language."""
    return ui(context.get("lang", "en"), key, **kwargs)
