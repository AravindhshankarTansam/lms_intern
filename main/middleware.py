from django.shortcuts import redirect
from .models import UserSession

class XFrameOptionsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response['X-Frame-Options'] = 'SAMEORIGIN'  # Or specify an allowed origin
        return response
    
class OneSessionPerUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if 'student_id' in request.session:
            user_id = request.session['student_id']
            user_type = 'student'
        elif 'faculty_id' in request.session:
            user_id = request.session['faculty_id']
            user_type = 'faculty'
        else:
            user_id = None
            user_type = None

        if user_id and user_type:
            try:
                user_session = UserSession.objects.get(user_id=user_id, user_type=user_type)
                print(user_session.session_key,'--', request.session.session_key)
                if user_session.session_key != request.session.session_key:
                    # Invalidate session and redirect to login
                    request.session.flush()
                    return redirect('std_login')
            except UserSession.DoesNotExist:
                pass

        response = self.get_response(request)
        return response