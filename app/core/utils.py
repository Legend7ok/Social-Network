from django.http import JsonResponse


def toggle_action(request, model, action_name, on_add, on_remove):
    obj_id = request.POST.get("id")
    action = request.POST.get("action")
    if obj_id and action:
        try:
            obj = model.objects.get(id=obj_id)
            if action == action_name:
                on_add(obj)
            else:
                on_remove(obj)

            return JsonResponse({"status": "ok"})

        except model.DoesNotExist:
            return JsonResponse({"status": "error"})

    return JsonResponse({"status": "error"})
