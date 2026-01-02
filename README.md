# 🎓 Better Grading System Than Your Teacher

> *"Why did my friend get an A but I got a B? We wrote almost the same thing!"*

Sound familiar? We've all been there. You pour your heart into an essay, submit it, and somehow your friend with basically the same answer gets a higher grade. What gives?

**The problem is simple: humans are biased.** Teachers get tired. They have favorites (even if they don't admit it). They might grade your paper after a bad cup of coffee. The first paper they read gets more attention than the 50th.

**This project fixes that.**

---

## 💡 What Is This?

This is an **AI-powered grading system** that evaluates student work with zero bias, zero favoritism, and zero emotions. It reads the rubric, reads your answer, and grades it **exactly** according to the criteria. Nothing more, nothing less.

### How It's Different From a Human Grader

| Human Grader | This System |
|-------------|-------------|
| Gets tired after 20 papers | Never gets tired |
| Might like certain students more | Has no idea who you are |
| Mood affects grading | Has no mood |
| Interprets rubric loosely | Follows rubric exactly |
| Inconsistent between papers | Same answer = Same grade, always |

---

## 🎯 Who Is This For?

- **Students** who want a fair, unbiased pre-grade before submitting
- **Teachers** who want to save time and ensure consistency
- **Schools** looking for standardized grading solutions
- **Anyone** who believes grading should be fair

---

## ⚡ Quick Demo

Here's what happened when we tested it with a climate change essay:

```
📝 Rubric: Essay Grading (100 points total)
   - Content Accuracy (30 pts)
   - Clarity of Expression (25 pts)
   - Supporting Evidence (25 pts)
   - Conclusion (20 pts)

📊 Result: 90/100 (A-)
   ✅ Content Accuracy: 30/30 - "Accurate facts about climate change"
   ✅ Clarity: 25/25 - "Clear and logical flow"
   ⚠️ Evidence: 20/25 - "Needs more diverse sources"
   ⚠️ Conclusion: 15/20 - "Could be stronger"
```

No favoritism. No bias. Just honest, rubric-based grading.

---

## 📋 Supported File Types

You can use any of these formats for your rubric or answer:

- 📄 **Text files** (.txt, .md)
- 📝 **Word documents** (.docx)
- 📊 **Excel spreadsheets** (.xlsx, .xls)
- 📕 **PDF files** (.pdf)

---

## 🚀 How to Set It Up

### Step 1: Install Python
Make sure you have **Python 3.11 or newer** installed. [Download Python here](https://www.python.org/downloads/) if you don't have it.

### Step 2: Download This Project
```bash
git clone <repository-url>
cd Better-Grading-System-Than-Your-Teacher
```

### Step 3: Create a Virtual Environment
This keeps the project's packages separate from your other Python stuff:

**On Windows:**
```bash
python -m venv .venv
.\.venv\Scripts\activate
```

**On Mac/Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Step 4: Install Everything
```bash
pip install -e ".[dev]"
```

### Step 5: You're Ready! 🎉

---

## 📖 How to Use It

### Grade a Student's Answer

```bash
strict-grader grade rubric.txt answer.txt -o report.json -v
```

This will:
1. Read your rubric file
2. Read the student's answer
3. Grade it with AI (3 passes for consistency!)
4. Save a detailed report

### Just Check If Your Rubric Is Good

```bash
strict-grader validate-rubric rubric.txt
```

### Make Sure Everything Is Working

```bash
strict-grader health
```

---

## 📝 Example Rubric Format

Your rubric can be as simple as:

```
Essay Grading Rubric

1. Content Accuracy (30 points): Answer must have correct facts
2. Clarity (25 points): Ideas should be clearly expressed
3. Evidence (25 points): Claims must be supported with examples
4. Conclusion (20 points): Must have a strong ending
```

That's it! The system will understand this format automatically.

---

## 🔒 Is My Data Safe?

Yes! Your documents are processed locally and sent only to the grading API. Nothing is stored permanently on external servers.

---

## 🧪 Running Tests

Want to make sure everything works? Run:

```bash
pytest tests/ -v
```

You should see **79 tests passing** ✅

---

## 🤔 FAQ

**Q: Can it grade creative writing?**
A: Yes, as long as you have a clear rubric. The AI needs criteria to grade against.

**Q: Does it work in languages other than English?**
A: The underlying AI supports many languages, but the system prompts are in English.

**Q: Can teachers cheat by knowing it's AI-graded?**
A: The grading is based purely on the rubric. There's nothing to "game" - just meet the criteria!

**Q: What if I disagree with the grade?**
A: Every grade comes with detailed justifications. You can see exactly why points were added or deducted.

---

## 💪 The Philosophy

We believe that grading should be:

1. **Fair** - Same work = Same grade, every time
2. **Transparent** - Clear reasons for every point
3. **Unbiased** - No favorites, no prejudice
4. **Consistent** - 8 AM or 8 PM, paper #1 or paper #100

This isn't about replacing teachers. It's about **helping them grade more fairly** while saving hours of repetitive work.

---

## 🛠️ Built With

- **Python 3.11+** - The programming language
- **ZenMux API** - AI grading powered by Gemini
- **PyMuPDF** - PDF reading
- **python-docx** - Word document reading
- **Pydantic** - Making sure all data is correct

---

## 📬 Questions?

Open an issue on GitHub or reach out. We'd love to hear how you're using it!

---

*Made by ClaRity Group, for students who deserve fair grades*
