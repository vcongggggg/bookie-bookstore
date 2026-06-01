INTERNAL_ROLES = ["Staff", "Manager", "Support", "Admin"]
ROLE_CHOICES = ["Customer", *INTERNAL_ROLES]

GROUP_PERMS = {
    "Staff": [
        "auth.view_user",
        "books.view_book",
        "books.view_coupon",
        "books.view_order",
        "books.view_orderitem",
    ],
    "Manager": [
        "books.view_book",
        "books.add_book",
        "books.change_book",
        "books.delete_book",
        "books.view_coupon",
        "books.view_order",
        "books.view_orderitem",
    ],
    "Support": [
        "books.view_order",
        "books.change_order",
        "books.view_orderitem",
    ],
    "Admin": [
        "auth.view_user",
        "auth.change_user",
        "books.view_book",
        "books.add_book",
        "books.change_book",
        "books.delete_book",
        "books.view_coupon",
        "books.add_coupon",
        "books.change_coupon",
        "books.delete_coupon",
        "books.view_order",
        "books.change_order",
        "books.view_orderitem",
        "books.view_adminauditlog",
    ],
}


def primary_role(user):
    if not user.is_authenticated:
        return "Customer"
    if user.is_superuser:
        return "Admin"
    role_names = set(user.groups.values_list("name", flat=True))
    for role in INTERNAL_ROLES:
        if role in role_names:
            return role
    return "Customer"
