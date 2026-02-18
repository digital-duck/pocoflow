"""PocoFlow Nested Batch — school grade processing.

Demonstrates: nested batch pattern with loops in a single node.
Original PocketFlow uses nested BatchFlow with self.params;
PocoFlow uses nested loops in exec().
No LLM needed — pure data processing.
"""

import os
from pocoflow import Node, Flow, Store


class LoadAndProcessGrades(Node):
    """Loads grade files from nested school/class/student directories."""

    def prep(self, store):
        school_dir = store["school_dir"]
        classes = sorted(
            d for d in os.listdir(school_dir)
            if os.path.isdir(os.path.join(school_dir, d))
        )
        return school_dir, classes

    def exec(self, prep_result):
        school_dir, classes = prep_result
        school_results = {}

        for class_name in classes:
            class_dir = os.path.join(school_dir, class_name)
            student_files = sorted(
                f for f in os.listdir(class_dir) if f.endswith(".txt")
            )

            class_results = {}
            for student_file in student_files:
                filepath = os.path.join(class_dir, student_file)
                with open(filepath) as f:
                    grades = [int(line.strip()) for line in f if line.strip()]

                student_name = os.path.splitext(student_file)[0]
                avg = sum(grades) / len(grades) if grades else 0
                class_results[student_name] = {
                    "grades": grades,
                    "average": round(avg, 1),
                    "highest": max(grades) if grades else 0,
                    "lowest": min(grades) if grades else 0,
                }
                print(f"  {class_name}/{student_name}: avg={avg:.1f}")

            school_results[class_name] = class_results

        return school_results

    def post(self, store, prep_result, exec_result):
        store["results"] = exec_result
        return "report"


class GenerateReport(Node):
    def prep(self, store):
        return store["results"]

    def exec(self, prep_result):
        return prep_result

    def post(self, store, prep_result, exec_result):
        results = prep_result
        print("\n===== School Report =====\n")
        for class_name, students in results.items():
            class_avgs = [s["average"] for s in students.values()]
            class_avg = sum(class_avgs) / len(class_avgs) if class_avgs else 0
            print(f"{class_name} (class average: {class_avg:.1f})")
            for name, stats in students.items():
                print(f"  {name}: avg={stats['average']}, "
                      f"high={stats['highest']}, low={stats['lowest']}")
            print()

        # Overall school average
        all_avgs = []
        for students in results.values():
            all_avgs.extend(s["average"] for s in students.values())
        school_avg = sum(all_avgs) / len(all_avgs) if all_avgs else 0
        print(f"School Average: {school_avg:.1f}")
        store["school_average"] = school_avg
        return "done"


def main():
    loader = LoadAndProcessGrades()
    report = GenerateReport()
    loader.then("report", report)

    store = Store(
        data={"school_dir": "school", "results": {}, "school_average": 0},
        name="nested_batch",
    )

    print("Processing school grades...\n")
    flow = Flow(start=loader)
    flow.run(store)


if __name__ == "__main__":
    main()
