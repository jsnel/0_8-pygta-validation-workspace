# TestCaseInitConc Validation Prompt

Similar to the other case studies, migrate and validate the following local Git repository:

[temp/case-studies/TestCaseInitConc/reference](temp/case-studies/TestCaseInitConc/reference/)

Its staging counterpart is:

[temp/case-studies/TestCaseInitConc/staging](temp/case-studies/TestCaseInitConc/staging/)

That means:

- Use the [pyglotaran v0.7-to-v0.8 migration skill](skills/pyglotaran-v07-to-v08-migration/SKILL.md) to migrate [20260905target_State1_2guide_8comp4test.ipynb](temp/case-studies/TestCaseInitConc/reference/20260905target_State1_2guide_8comp4test.ipynb) from main to staging syntax.
- Run a comparison of the reference/main and staging outcomes, then report the results.

This extends the previous validation plan in [case-study-validation-plan.md](case-study-validation-plan.md) to a new case study. The reference and staging folders already exist; complete the remaining setup and validation work.

The case study notebook is also available one level above the repositories:

[temp/case-studies/TestCaseInitConc/20260905target_State1_2guide_8comp4test.ipynb](temp/case-studies/TestCaseInitConc/20260905target_State1_2guide_8comp4test.ipynb)

The latest reference results are located at:

[temp/case-studies/TestCaseInitConc/reference/results](temp/case-studies/TestCaseInitConc/reference/results/)

The reference repository should be runnable with main, and the staging repository should be runnable with staging after migration.