import os
from django.conf import settings
import datetime
from django.shortcuts import render, redirect, get_object_or_404
from .models import Quiz, Question, StudentAnswer, CertificateDownload
from main.models import Student, Course, Faculty, Assignment, Submission
from main.views import is_faculty_authorised, is_student_authorised
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Sum, F, FloatField, Q, Prefetch
from django.db.models.functions import Cast
from django.http import JsonResponse, HttpResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import fitz  

def quiz(request, code):
    try:
        course = Course.objects.get(code=code)
        if is_faculty_authorised(request, code):
            if request.method == 'POST':
                title = request.POST.get('title')
                description = request.POST.get('description')
                start = request.POST.get('start')
                end = request.POST.get('end')
                publish_status = request.POST.get('checkbox')
                quiz = Quiz(title=title, description=description, start=start,
                            end=end, publish_status=publish_status, course=course)
                quiz.save()
                return redirect('addQuestion', code=code, quiz_id=quiz.id)
            else:
                return render(request, 'quiz/quiz.html', {'course': course, 'faculty': Faculty.objects.get(faculty_id=request.session['faculty_id'])})

        else:
            return redirect('std_login')
    except:
        return render(request, 'error.html')


def addQuestion(request, code, quiz_id):
    try:
        course = Course.objects.get(code=code)
        if is_faculty_authorised(request, code):
            quiz = Quiz.objects.get(id=quiz_id)
            if request.method == 'POST':
                question = request.POST.get('question')
                option1 = request.POST.get('option1')
                option2 = request.POST.get('option2')
                option3 = request.POST.get('option3')
                option4 = request.POST.get('option4')
                answer = request.POST.get('answer')
                marks = request.POST.get('marks')
                explanation = request.POST.get('explanation')
                question = Question(question=question, option1=option1, option2=option2,
                                    option3=option3, option4=option4, answer=answer, quiz=quiz, marks=marks, explanation=explanation)
                question.save()
                messages.success(request, 'Question added successfully')
            else:
                return render(request, 'quiz/addQuestion.html', {'course': course, 'quiz': quiz, 'faculty': Faculty.objects.get(faculty_id=request.session['faculty_id'])})
            if 'saveOnly' in request.POST:
                return redirect('allQuizzes', code=code)
            return render(request, 'quiz/addQuestion.html', {'course': course, 'quiz': quiz, 'faculty': Faculty.objects.get(faculty_id=request.session['faculty_id'])})
        else:
            return redirect('std_login')
    except:
        return render(request, 'error.html')


def allQuizzes(request, code):
    if is_faculty_authorised(request, code):
        course = Course.objects.get(code=code)
        quizzes = Quiz.objects.filter(course=course)
        for quiz in quizzes:
            quiz.total_questions = Question.objects.filter(quiz=quiz).count()
            if quiz.start < datetime.datetime.now():
                quiz.started = True
            else:
                quiz.started = False
            quiz.save()
        return render(request, 'quiz/allQuizzes.html', {'course': course, 'quizzes': quizzes, 'faculty': Faculty.objects.get(faculty_id=request.session['faculty_id'])})
    else:
        return redirect('std_login')


def myQuizzes(request, code):
    if is_student_authorised(request, code):
        course = Course.objects.get(code=code)
        quizzes = Quiz.objects.filter(course=course)
        student = Student.objects.get(student_id=request.session['student_id'])

        # Determine which quizzes are active and which are previous
        active_quizzes = []
        previous_quizzes = []
        for quiz in quizzes:
            if quiz.end < timezone.now() or quiz.studentanswer_set.filter(student=student).exists():
                previous_quizzes.append(quiz)
            else:
                active_quizzes.append(quiz)

        # Add attempted flag to quizzes
        for quiz in quizzes:
            quiz.attempted = quiz.studentanswer_set.filter(
                student=student).exists()

        # Add total marks obtained, percentage, and total questions for previous quizzes
        for quiz in previous_quizzes:
            student_answers = quiz.studentanswer_set.filter(student=student)
            total_marks_obtained = sum([student_answer.question.marks if student_answer.answer ==
                                       student_answer.question.answer else 0 for student_answer in student_answers])
            quiz.total_marks_obtained = total_marks_obtained
            quiz.total_marks = sum(
                [question.marks for question in quiz.question_set.all()])
            quiz.percentage = round(
                total_marks_obtained / quiz.total_marks * 100, 2) if quiz.total_marks != 0 else 0
            quiz.total_questions = quiz.question_set.count()

        # Add total questions for active quizzes
        for quiz in active_quizzes:
            quiz.total_questions = quiz.question_set.count()

        return render(request, 'quiz/myQuizzes.html', {
            'course': course,
            'quizzes': quizzes,
            'active_quizzes': active_quizzes,
            'previous_quizzes': previous_quizzes,
            'student': student,
        })
    else:
        return redirect('std_login')


def startQuiz(request, code, quiz_id):
    if is_student_authorised(request, code):
        course = Course.objects.get(code=code)
        quiz = Quiz.objects.get(id=quiz_id)
        questions = Question.objects.filter(quiz=quiz)
        total_questions = questions.count()

        marks = 0
        for question in questions:
            marks += question.marks
        quiz.total_marks = marks

        return render(request, 'quiz/portalStdNew.html', {'course': course, 'quiz': quiz, 'questions': questions, 'total_questions': total_questions, 'student': Student.objects.get(student_id=request.session['student_id'])})
    else:
        return redirect('std_login')


def studentAnswer(request, code, quiz_id):
    if is_student_authorised(request, code):
        course = Course.objects.get(code=code)
        quiz = Quiz.objects.get(id=quiz_id)
        questions = Question.objects.filter(quiz=quiz)
        student = Student.objects.get(student_id=request.session['student_id'])

        for question in questions:
            answer = request.POST.get(str(question.id))
            student_answer = StudentAnswer(student=student, quiz=quiz, question=question,
                                           answer=answer, marks=question.marks if answer == question.answer else 0)
            # prevent duplicate answers & multiple attempts
            try:
                student_answer.save()
            except:
                redirect('myQuizzes', code=code)
        return redirect('myQuizzes', code=code)
    else:
        return redirect('std_login')


def quizResult(request, code, quiz_id):
    if is_student_authorised(request, code):
        course = Course.objects.get(code=code)
        quiz = Quiz.objects.get(id=quiz_id)
        questions = Question.objects.filter(quiz=quiz)
        try:
            student = Student.objects.get(
                student_id=request.session['student_id'])
            student_answers = StudentAnswer.objects.filter(
                student=student, quiz=quiz)
            total_marks_obtained = 0
            for student_answer in student_answers:
                total_marks_obtained += student_answer.question.marks if student_answer.answer == student_answer.question.answer else 0
            quiz.total_marks_obtained = total_marks_obtained
            quiz.total_marks = 0
            for question in questions:
                quiz.total_marks += question.marks
            quiz.percentage = (total_marks_obtained / quiz.total_marks) * 100
            quiz.percentage = round(quiz.percentage, 2)
        except:
            quiz.total_marks_obtained = 0
            quiz.total_marks = 0
            quiz.percentage = 0

        for question in questions:
            student_answer = StudentAnswer.objects.get(
                student=student, question=question)
            question.student_answer = student_answer.answer

        student_answers = StudentAnswer.objects.filter(
            student=student, quiz=quiz)
        for student_answer in student_answers:
            quiz.time_taken = student_answer.created_at - quiz.start
            quiz.time_taken = quiz.time_taken.total_seconds()
            quiz.time_taken = round(quiz.time_taken, 2)
            quiz.submission_time = student_answer.created_at.strftime(
                "%a, %d-%b-%y at %I:%M %p")
        return render(request, 'quiz/quizResult.html', {'course': course, 'quiz': quiz, 'questions': questions, 'student': student})
    else:
        return redirect('std_login')


def quizSummary(request, code, quiz_id):
    if is_faculty_authorised(request, code):
        course = Course.objects.get(code=code)
        quiz = Quiz.objects.get(id=quiz_id)

        questions = Question.objects.filter(quiz=quiz)
        time = datetime.datetime.now()
        total_students = Student.objects.filter(course=course).count()
        for question in questions:
            question.A = StudentAnswer.objects.filter(
                question=question, answer='A').count()
            question.B = StudentAnswer.objects.filter(
                question=question, answer='B').count()
            question.C = StudentAnswer.objects.filter(
                question=question, answer='C').count()
            question.D = StudentAnswer.objects.filter(
                question=question, answer='D').count()
        # students who have attempted the quiz and their marks
        students = Student.objects.filter(course=course)
        for student in students:
            student_answers = StudentAnswer.objects.filter(
                student=student, quiz=quiz)
            total_marks_obtained = 0
            for student_answer in student_answers:
                total_marks_obtained += student_answer.question.marks if student_answer.answer == student_answer.question.answer else 0
            student.total_marks_obtained = total_marks_obtained

        if request.method == 'POST':
            quiz.publish_status = True
            quiz.save()
            return redirect('quizSummary', code=code, quiz_id=quiz.id)
        # check if student has attempted the quiz
        for student in students:
            if StudentAnswer.objects.filter(student=student, quiz=quiz).count() > 0:
                student.attempted = True
            else:
                student.attempted = False
        for student in students:
            student_answers = StudentAnswer.objects.filter(
                student=student, quiz=quiz)
            for student_answer in student_answers:
                student.submission_time = student_answer.created_at.strftime(
                    "%a, %d-%b-%y at %I:%M %p")

        context = {'course': course, 'quiz': quiz, 'questions': questions, 'time': time, 'total_students': total_students,
                   'students': students, 'faculty': Faculty.objects.get(faculty_id=request.session['faculty_id'])}
        return render(request, 'quiz/quizSummaryFaculty.html', context)

    else:
        return redirect('std_login')
    


def certificate_download(request, code):
    student_id = request.session.get('student_id')
    
    if not student_id:
        messages.error(request, 'Student ID not found in session.')
        return redirect('course', code=code)
    
    try:
        course = get_object_or_404(Course, code=code)
        course_code = course.code
        
        # Get quiz and assignment data
        quizzes = Quiz.objects.filter(course_id=course_code)
        quiz_ids = quizzes.values_list('id', flat=True)
        
        total_quiz_marks = Question.objects.filter(quiz_id__in=quiz_ids).aggregate(total_marks=Sum('marks'))['total_marks'] or 0
        obtained_quiz_marks = StudentAnswer.objects.filter(student_id=student_id, quiz_id__in=quiz_ids).aggregate(marks_obtained=Sum('marks'))['marks_obtained'] or 0
        
        # Check if student has submitted the assignment
        assignment = get_object_or_404(Assignment, course_code=course_code)
        total_assignment_marks = assignment.marks
        obtained_assignment_marks = Submission.objects.filter(student_id=student_id, assignment_id=assignment.id).aggregate(marks_obtained=Sum('marks'))['marks_obtained'] or 0
        
        if total_quiz_marks == 0 or total_assignment_marks == 0:
            messages.error(request, 'No quizzes or Assignment found for this course.')
            return redirect('course', code=code)
        
        # Total marks and marks obtained including both quizzes and assignment
        total_marks = total_quiz_marks + total_assignment_marks
        marks_obtained = obtained_quiz_marks + obtained_assignment_marks
        
        # Check if the student has submitted both quizzes and assignment
        if obtained_quiz_marks == 0 or obtained_assignment_marks == 0:
            messages.error(request, 'Student has not submitted both quizzes and assignments.')
            return redirect('course', code=code)
        
        percentage = (marks_obtained / total_marks) * 100
        
        # Determine certificate template
        template_path = 'C:/LMS_NEW/eLMS-SWE/media/certificates/templates/ONLINE_CERTIFICATION_FAIL.pdf'
        if percentage >= 95:
            template_path = 'C:/LMS_NEW/eLMS-SWE/media/certificates/templates/ONLINE_CERTIFICATION_Gold.pdf'
        elif percentage >= 80:
            template_path = 'C:/LMS_NEW/eLMS-SWE/media/certificates/templates/ONLINE_CERTIFICATION_Silver.pdf'
        elif percentage >= 75:
            template_path = 'C:/LMS_NEW/eLMS-SWE/media/certificates/templates/ONLINE_CERTIFICATION_BRONZE.pdf'
        
        student = get_object_or_404(Student, student_id=student_id)
        student_name = student.name
    
        output_pdf_path = os.path.join(settings.MEDIA_ROOT, 'certificates/certificate_{}.pdf'.format(student_id))
        
        # Generate the certificate PDF
        pdf_document = fitz.open(template_path)
        page = pdf_document[0]
        
        font_size = 18
        student_name_position = (340, 280)  
        percentage_position = (505, 380)
        quiz_marks_position = (320, 418)
        project_marks_position = (580, 418)

        # Draw the student name, percentage, quiz marks, project marks
        page.insert_text(student_name_position, student_name, fontsize=font_size, color=(0, 0, 0))
        page.insert_text(percentage_position, f"{percentage:.2f}", fontsize=font_size, color=(0, 0, 0))
        page.insert_text(quiz_marks_position, str(obtained_quiz_marks), fontsize=font_size, color=(0, 0, 0))
        page.insert_text(project_marks_position, str(obtained_assignment_marks), fontsize=font_size, color=(0, 0, 0))
        
        # Save the modified PDF
        pdf_document.save(output_pdf_path)
        pdf_document.close()
        
        # Log the certificate download
        CertificateDownload.objects.create(
            student_id=student_id,
            course_id=course_code,
            file_path=output_pdf_path,
            download_timestamp=timezone.now(),
            percentage=percentage
        )
        
        # Serve the PDF file for download
        with open(output_pdf_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="certificate_{student_id}.pdf"'
            return response
        
    except Course.DoesNotExist:
        messages.error(request, 'Course not found.')
        return redirect('course', code=code)
    except Exception as e:
        messages.error(request,'Something went wrong. Please try again later.')
        return redirect('course', code=code)