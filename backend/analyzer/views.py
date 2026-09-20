import json

from django.utils import timezone
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    parser_classes,
    permission_classes,
)
from rest_framework.generics import GenericAPIView
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .authentication import FirebaseAuthentication
from .models import InterviewQuestion, MockInterview, ResumeAnalysis
from .serializers import ResumeUploadSerializer
from .services.ai_analyzer import analyze_resume, parse_resume_structure
from .services.interview_service import (
    evaluate_answer,
    generate_questions,
    generate_summary,
)
from .services.pdf_parser import extract_docx_text, extract_pdf_text

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------


def _extract_resume_text(resume_file):
    """Extract text from a PDF or DOCX file object. Returns (text, error_response)."""
    file_name = resume_file.name.lower()
    if file_name.endswith(".pdf"):
        try:
            text = extract_pdf_text(resume_file)
        except Exception as exc:
            return None, Response(
                {"success": False, "error": f"Failed to read PDF: {exc}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
    elif file_name.endswith(".docx"):
        try:
            text = extract_docx_text(resume_file)
        except Exception as exc:
            return None, Response(
                {"success": False, "error": f"Failed to read DOCX: {exc}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
    else:
        return None, Response(
            {"success": False, "error": "Only PDF and DOCX files are supported."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not text or len(text.strip()) < 20:
        return None, Response(
            {
                "success": False,
                "error": "Could not extract readable text from the resume. "
                "Ensure it is not a scanned image-only PDF.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    return text, None


# ---------------------------------------------------------------------------
# UPLOAD RESUME (text extraction only)
# ---------------------------------------------------------------------------


class UploadResumeView(GenericAPIView):
    serializer_class = ResumeUploadSerializer
    parser_classes = [MultiPartParser, FormParser]
    authentication_classes = [FirebaseAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"success": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        resume = serializer.validated_data["resume"]
        text, err = _extract_resume_text(resume)
        if err:
            return err

        return Response(
            {
                "success": True,
                "user": {
                    "id": request.user.id,
                    "firebase_uid": request.user.firebase_uid,
                    "email": request.user.email,
                },
                "filename": resume.name,
                "text": text,
            },
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# ANALYZE RESUME (AI analysis + structured extraction + save to history)
# ---------------------------------------------------------------------------


class AnalyzeResumeView(GenericAPIView):
    serializer_class = ResumeUploadSerializer
    parser_classes = [MultiPartParser, FormParser]
    authentication_classes = [FirebaseAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"success": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        resume = serializer.validated_data["resume"]
        job_description = serializer.validated_data.get("job_description", "").strip()

        # Enforce non-empty job description
        if not job_description:
            return Response(
                {
                    "success": False,
                    "error": "Job description is required and cannot be empty. "
                    "Provide a job description to enable JD match scoring.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Extract resume text
        text, err = _extract_resume_text(resume)
        if err:
            return err

        try:
            # 1. Structured resume extraction (uses RESUME_SCHEMA)
            structured_resume = parse_resume_structure(text)

            # 2. AI analysis (JD match, scores, suggestions)
            analysis = analyze_resume(resume_text=text, job_description=job_description)

            # Attach structured data to the analysis payload
            analysis["structured_resume"] = structured_resume

        except RuntimeError as exc:
            return Response(
                {"success": False, "error": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except Exception as exc:
            return Response(
                {"success": False, "error": f"Analysis failed: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # 3. Save to database
        overall_score = int(analysis.get("overall_score") or 0)
        summary = str(analysis.get("summary") or "")

        saved_record = ResumeAnalysis.objects.create(
            user=request.user,
            filename=resume.name,
            overall_score=overall_score,
            job_description=job_description,
            summary=summary,
            analysis_data=analysis,
        )

        return Response(
            {
                "success": True,
                "analysis_id": saved_record.id,
                "user": {
                    "id": request.user.id,
                    "firebase_uid": request.user.firebase_uid,
                    "email": request.user.email,
                },
                "filename": resume.name,
                "created_at": saved_record.created_at.isoformat(),
                "analysis": analysis,
            },
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# DASHBOARD (user stats & past analyses)
# ---------------------------------------------------------------------------


@api_view(["GET"])
@authentication_classes([FirebaseAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def dashboard(request):
    user = request.user
    analyses_qs = ResumeAnalysis.objects.filter(user=user).order_by("-created_at")

    total_scans = analyses_qs.count()
    highest_record = analyses_qs.order_by("-overall_score", "-created_at").first()
    lowest_record = analyses_qs.order_by("overall_score", "-created_at").first()

    past_analyses = [
        {
            "id": a.id,
            "filename": a.filename,
            "overall_score": a.overall_score,
            "summary": a.summary,
            "has_job_description": bool(a.job_description),
            "created_at": a.created_at.isoformat(),
        }
        for a in analyses_qs[:20]  # newest 20 scans
    ]

    return Response(
        {
            "success": True,
            "user": {
                "id": user.id,
                "firebase_uid": user.firebase_uid,
                "email": user.email,
                "name": user.name,
                "photo_url": user.photo_url,
                "created_at": user.created_at.isoformat() if user.created_at else None,
            },
            "stats": {
                "total_scans": total_scans,
                "highest_score": highest_record.overall_score if highest_record else None,
                "highest_resume_name": highest_record.filename if highest_record else None,
                "lowest_score": lowest_record.overall_score if lowest_record else None,
                "lowest_resume_name": lowest_record.filename if lowest_record else None,
            },
            "past_analyses": past_analyses,
        }
    )


# ---------------------------------------------------------------------------
# SINGLE ANALYSIS DETAIL & DELETE
# ---------------------------------------------------------------------------


@api_view(["GET", "DELETE"])
@authentication_classes([FirebaseAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def analysis_detail(request, analysis_id):
    try:
        # user=request.user enforces ownership — users can only see their own records
        record = ResumeAnalysis.objects.get(id=analysis_id, user=request.user)
    except ResumeAnalysis.DoesNotExist:
        return Response(
            {"success": False, "error": "Analysis record not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "DELETE":
        record.delete()
        return Response(
            {"success": True, "message": "Analysis record deleted successfully."},
            status=status.HTTP_200_OK,
        )

    return Response(
        {
            "success": True,
            "id": record.id,
            "filename": record.filename,
            "overall_score": record.overall_score,
            "job_description": record.job_description,
            "summary": record.summary,
            "created_at": record.created_at.isoformat(),
            "analysis": record.analysis_data,
        },
        status=status.HTTP_200_OK,
    )


# ---------------------------------------------------------------------------
# TEST AUTH
# ---------------------------------------------------------------------------


@api_view(["GET"])
@authentication_classes([FirebaseAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def test_auth(request):
    return Response(
        {
            "success": True,
            "message": "Firebase authentication successful.",
            "user": {
                "id": request.user.id,
                "firebase_uid": request.user.firebase_uid,
                "email": request.user.email,
                "name": request.user.name,
                "photo_url": request.user.photo_url,
            },
        },
        status=status.HTTP_200_OK,
    )


# ---------------------------------------------------------------------------
# MOCK INTERVIEW — START (generate questions from structured resume data)
# ---------------------------------------------------------------------------


@api_view(["POST"])
@authentication_classes([FirebaseAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def start_interview(request):
    """Creates a new interview session by parsing uploaded PDF/DOCX resume and generating 10 questions."""
    job_role = request.data.get("job_role", "").strip()
    resume_file = request.FILES.get("file") or request.FILES.get("resume")
    resume_text = request.data.get("resume_text", "").strip()

    if not job_role:
        return Response(
            {"error": "Please provide a target job role (e.g. Frontend Developer)."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if resume_file:
        file_name = resume_file.name.lower()
        if not (file_name.endswith(".pdf") or file_name.endswith(".docx")):
            return Response(
                {"error": "Unsupported file format. Please upload a PDF or DOCX resume."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            if file_name.endswith(".pdf"):
                resume_text = extract_pdf_text(resume_file)
            else:
                resume_text = extract_docx_text(resume_file)
        except Exception as exc:
            return Response(
                {"error": f"Failed to extract text from resume file: {exc}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    if not resume_text or len(resume_text.strip()) < 30:
        return Response(
            {"error": "Please upload a valid PDF or DOCX resume with readable content."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Extract structured resume data to enrich question generation context
    try:
        structured_resume = parse_resume_structure(resume_text)
    except Exception:
        structured_resume = {}

    try:
        questions_data = generate_questions(resume_text, job_role, structured_resume)
    except Exception as exc:
        return Response(
            {"error": f"Failed to generate interview questions: {exc}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # Save interview session
    interview = MockInterview.objects.create(
        user=request.user,
        job_role=job_role,
        resume_text=resume_text,
        status="in_progress",
    )

    # Save questions
    saved_questions = []
    for i, q in enumerate(questions_data):
        q_text = q.get("question", "")
        q_type = q.get("type", "technical")
        default_diff = "Easy" if i < 2 else "Medium" if i < 5 else "Hard" if i < 7 else "Behavioral"
        q_diff = q.get("difficulty", default_diff)

        question_obj = InterviewQuestion.objects.create(
            interview=interview,
            order=i + 1,
            question_text=q_text,
            question_type=q_type,
        )
        saved_questions.append(
            {
                "id": question_obj.id,
                "order": question_obj.order,
                "question": question_obj.question_text,
                "type": question_obj.question_type,
                "difficulty": q_diff,
            }
        )

    return Response(
        {
            "interview_id": interview.id,
            "job_role": interview.job_role,
            "questions": saved_questions,
        },
        status=status.HTTP_201_CREATED,
    )


# ---------------------------------------------------------------------------
# MOCK INTERVIEW — SUBMIT ANSWER
# ---------------------------------------------------------------------------


@api_view(["POST"])
@authentication_classes([FirebaseAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def submit_answer(request, interview_id):
    """Submit and evaluate one answer for a specific question."""
    try:
        # Ownership enforced via user=request.user
        interview = MockInterview.objects.get(id=interview_id, user=request.user)
    except MockInterview.DoesNotExist:
        return Response({"error": "Interview session not found."}, status=status.HTTP_404_NOT_FOUND)

    question_id = request.data.get("question_id")
    answer = request.data.get("answer", "").strip()

    if not question_id or not answer:
        return Response(
            {"error": "question_id and answer are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        question_obj = InterviewQuestion.objects.get(id=question_id, interview=interview)
    except InterviewQuestion.DoesNotExist:
        return Response({"error": "Question not found."}, status=status.HTTP_404_NOT_FOUND)

    try:
        feedback = evaluate_answer(
            question=question_obj.question_text,
            answer=answer,
            resume_text=interview.resume_text,
            job_role=interview.job_role,
        )
    except Exception as exc:
        return Response(
            {"error": f"Failed to evaluate answer: {exc}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # Persist the answer and feedback using the correct model fields
    question_obj.user_answer = answer
    question_obj.ai_score = feedback.get("overall", 0)
    question_obj.ai_feedback = feedback
    question_obj.answered_at = timezone.now()
    question_obj.save()

    return Response(
        {"question_id": question_obj.id, "feedback": feedback},
        status=status.HTTP_200_OK,
    )


# ---------------------------------------------------------------------------
# MOCK INTERVIEW — FINISH (generate overall summary)
# ---------------------------------------------------------------------------


@api_view(["POST"])
@authentication_classes([FirebaseAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def finish_interview(request, interview_id):
    """Finalise a session — generate and save overall performance summary."""
    try:
        interview = MockInterview.objects.get(id=interview_id, user=request.user)
    except MockInterview.DoesNotExist:
        return Response({"error": "Interview session not found."}, status=status.HTTP_404_NOT_FOUND)

    answered_qs = interview.questions.filter(user_answer__isnull=False)
    if not answered_qs.exists():
        return Response(
            {"error": "No answers found for this interview."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    qa_pairs = [
        {
            "question": q.question_text,
            "answer": q.user_answer,
            "score": q.ai_score or 0,
        }
        for q in answered_qs
    ]

    try:
        summary = generate_summary(job_role=interview.job_role, qa_pairs=qa_pairs)
    except Exception as exc:
        return Response(
            {"error": f"Failed to generate summary: {exc}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    interview.overall_score = summary.get("overall_score", 0)
    interview.performance_summary = json.dumps(summary)
    interview.status = "completed"
    interview.save()

    return Response(
        {"interview_id": interview.id, "summary": summary},
        status=status.HTTP_200_OK,
    )


# ---------------------------------------------------------------------------
# MOCK INTERVIEW — HISTORY
# ---------------------------------------------------------------------------


@api_view(["GET"])
@authentication_classes([FirebaseAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def interview_history(request):
    """Return a list of past interview sessions for the authenticated user."""
    interviews = MockInterview.objects.filter(user=request.user).order_by("-created_at")[:20]

    data = []
    for iv in interviews:
        summary_obj = None
        if iv.performance_summary:
            try:
                summary_obj = json.loads(iv.performance_summary)
            except (json.JSONDecodeError, TypeError):
                pass

        data.append(
            {
                "id": iv.id,
                "job_role": iv.job_role,
                "status": iv.status,
                "overall_score": iv.overall_score,
                "question_count": iv.questions.count(),
                "answered_count": iv.questions.filter(user_answer__isnull=False).count(),
                "verdict": summary_obj.get("verdict") if summary_obj else None,
                "created_at": iv.created_at.isoformat(),
            }
        )

    return Response({"interviews": data}, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# MOCK INTERVIEW — DETAIL
# Fixed: use correct model fields ai_feedback, question_type, ai_score
# ---------------------------------------------------------------------------


@api_view(["GET"])
@authentication_classes([FirebaseAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def interview_detail(request, interview_id):
    """Return full details, question breakdown, and summary of a past interview."""
    try:
        # Ownership enforced via user=request.user
        interview = MockInterview.objects.get(id=interview_id, user=request.user)
    except MockInterview.DoesNotExist:
        return Response({"error": "Interview session not found."}, status=status.HTTP_404_NOT_FOUND)

    summary_obj = None
    if interview.performance_summary:
        try:
            summary_obj = json.loads(interview.performance_summary)
        except (json.JSONDecodeError, TypeError):
            pass

    questions = []
    for q in interview.questions.all().order_by("order"):
        # ai_feedback is a JSONField — already a dict, no json.loads needed
        questions.append(
            {
                "id": q.id,
                "question": q.question_text,
                "question_type": q.question_type,  # was: category / difficulty (wrong)
                "user_answer": q.user_answer,
                "ai_score": q.ai_score,  # was: score (wrong)
                "ai_feedback": q.ai_feedback,  # was: feedback with json.loads (wrong)
            }
        )

    return Response(
        {
            "id": interview.id,
            "job_role": interview.job_role,
            "status": interview.status,
            "overall_score": interview.overall_score,
            "created_at": interview.created_at.isoformat(),
            "summary": summary_obj,
            "questions": questions,
        },
        status=status.HTTP_200_OK,
    )
