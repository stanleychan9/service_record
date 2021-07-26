# Service Record: A web application for students and teachers
#### Video Demo: https://www.youtube.com/watch?v=DpyCnx76HgA
#### Description:

# Background

## Situation

This private personal project is created with inspiration from the existing student service record system of my serving school. In every school year, students provide services in school and to the community through different positions e.g. Chairperson of Class Club, Treasurer of Science Society, Vice-captain of the School Tennis Team, volunteer of a community event outside school, etc.

At the end of each school year, different parties involved need to carry out the following procedures:
1. Students are required to write down their service records in a paper-based service record book.
2. Students need to ask teachers or persons responsible for external services to sign in the service record book for verification.
3. Form teachers need to collect service record books of students of their respective classes, and hand in to the teacher-coordinator for it. If a student loses her/his book, s/he needs to submit a parent's letter to the form teacher.
4. Administrative staff of the school need to manually enter the records into a computer for storing the records and determining the award to be received by each student.

## Difficulties

Given that there are almost 1,000 students and 60 teachers in a school, the above procedures can be daunting:
- Approaching the end of a school year, many students need to line up to ask for teachers' signature.
- Form teachers need to keep asking students of their classes to submit the service record book. They also need to keep track of the students who have lost the book.
- Some form teachers may not emphasise this task so much and the teacher-coordinator needs to spend much time on asking those form teachers to collect and submit their classes' service record books.
- Much time is required to manually enter the records into a computer and double-check the entry of the data.

# Design Overview

## Tasks to be handled

In light of the current difficulties, this flask web application is largely an online service record management system to automate most of the administrative procedures. Major tasks that this web application handles include:
- allowing students to enter service records online;
- allowing teachers to review and endorse / reject the records related to them;
- calculating the total number of service hours endorsed by teachers;
- allowing the administrator to generate service awards of all students with one click; and
- allowing the administrator to export a CSV file of all students' service hours and awards.

## Database
This web application heavily involves a database, `service.db`, that stores the information of different aspects. This database contains the following tables:
- `students` - storing student numbers, names, classes, class numbers, service hours, awards, etc.;
- `teachers` - storing teacher names, rights to endorse external records, etc.;
- `organisations` - storing names of school organisations (e.g. clubs and societies), teachers-in-charge, etc.;
- `int_records` - storing internal service records submitted by students, their status (e.g. pending / endorsed / rejected), etc.; and
- `ext_records` - similar to int\_records, but it is for storing external service records.

## NOT mobile-friendly

Most of the HTML pages of this web application involve one or two tables that show the information of students, their service records, etc. Due to the amount of information to be shown, some tables may include quite a number of columns. Therefore, this web application is temporarily ***not*** a mobile-friendly one.

In the paragraphs below, more information about the design of this web application will be explained with the following framework.
- Index page
- Account initialisation
- Log in / Log out
- Records entry
- Records review
- Awards generation and overview
- Student list exportation
- Manage organisation

# Index page

When accessing the default route, the user can see the index page of the web application. If the user wants to know more about service record, s/he can click "About Service Record" in the topbar for more information.

# Account initialisation

By default, a CSV file containing all students' information and teachers' information are imported into the `students` and `teachers` tables respectively. Each student / teacher is assigned with a random six-digit number as a personal code (stored in the `hash` column of each table), which is useful for the user's first time log in.

When clicking "Student Log In" in the topbar, the user can choose the class and class number and enter the personal code. The information is then POSTed to the `student_login` route, and the function `student_login()` is called. The function checks whether the class and class number are valid (e.g. class 6C has less than 32 students, and the web application will flash "No such student." when the user chooses to sign in as 6C(32)). The function also checks whether the personal code matches with the record in the `students` table.

If the personal code and other information is correct after checking the `students` table, the user is then brought to `student_createpw.html` to create a personal password, which should include at least one letter and one number. When the password created meets the requirement, the new password is POSTed to the `student_createpw` route with the function `student_createpw()` called. The password then replaces the original personal code in the `students` table, officially becoming the password to be used to sign in. Thanks to the module `werkzeug.security` that the password saved in the `students` table is hashed so that people obtaining this table cannot easily know what the password is.

For a teacher's first-time log in, the steps are largely the same as a student's. When a teacher needs to log in, s/he needs to use the email log in ID (e.g. "kkchan" for the teacher named "KK Chan"). Another difference is that table `teachers` is involved, instead of `students`.

# Log In / Log Out

When self-creating the password during first-time log in, the user is also logged in as that student / teacher. The sign-in information is also shown in the `footer` of each page.

After creating the password, the user remained logged in. To log out, simply click "Log Out" in the topbar. To log in again, click "Teacher Log In" or "Student Log In".

# Records entry

When a user has logged in as a student, s/he can enter her/his service records. (If a user not signed in as a student tries to access the following pages, s/he will be rejected.)

## Internal records

To enter internal service records, click "Add Internal Records" in the topbar. The user needs to choose the organisation or activity in the select menu. JavaScript is added in this page to allow the page to display different input fields based on the user's choice.

When the user chooses some default school organisation (e.g. Choir, Netball Team, etc.), the user is allowed to enter information about the post and number of service hours. When the user chooses "Subject Leader", the user is asked to choose the class, subject, and subject teacher. When the user chooses "Others" (e.g. the student offers help in an ad hoc school function), the user is asked to specify the organisation or activity and choose the teacher responsible for it.

The information is then POSTed to the route `add_int_record`. Function `add_int_record()` is called, and the above information is stored in the `int_records` table, with the `status` of the record being default i.e. "pending".

## External records

For entering external service records, click "Add External Records" in the topbar. The user then fills in the information about the external service, including contact information of the external organisation / activity so that the school can ask for more information about this service experience if necessary. The information is then POSTed to the route `add_ext_record`. Function `add_ext_record()` is called, and the above information is stored in the `ext_records` table, with the `status` of the record being default i.e. "pending".

## Delete records

After a student has entered the record, s/he can review her records when clicking "My Records" in the topbar. Normally, s/he can see the record just submitted with the status "pending" i.e. it has not yet been reviewed by the teacher. When the student discovers some mistakes in the record, s/he can click "Delete" to delete the record and enter a correct record again with the methods above. When the record is deleted, the information is POSTed to the route `myrecords` and the function `myrecords()` is called. The status information in the `int_records` or `ext_records` table is then updated to be "deleted".

# Records review

When a user has logged in as a teacher, s/he can enter her/his service records. (If a user not signed in as a teacher tries to access the following pages, s/he will be rejected.)

## Internal records

When a teacher clicks "Review Records" in the topbar, a table showing students' internal service records is shown. Note that ***not*** all students' records are shown - by joining the tables `int_records` and `organisations`, the teacher can only see the records related to her/him e.g. service related to the school organisations that s/he is responsible for, subject leader records with s/he being the subject teacher, etc. Records deleted by the student are not shown as well. Without these measures, the table would be very long and the teachers would certainly be overwhelmed.

In the table, the teacher can do the either or both of the following.
- Changing the number of hours: The teacher can change the number of hours of a record if needed.
- Changing the status: The teacher can change the status of a record e.g. when endorsing a record, the teacher chooses "Endorsed" in the status column. The teacher can still change it back to other statuses e.g. "Pending" or "Rejected".

As each row is an individual form, the teacher need to click "Change" for each record one by one. This can allow the teacher to more carefully review each individual record. When clicking change, the information of this record is POSTed to the route `review`, and the function `reivew()` is called. The information in `int_records` (`hours` and `status`) and `students` (`total_hours`) are both updated.

## External records

Only teachers with the `external` column being "1" in the `teachers` table have the right to review external records. If s/he has this right, s/he can click "Review External Records" to view all students' external service records. The teacher can also change the number of hours and status of each record like s/he does for internal records mentioned above. The information is POSTed to the route `reviewext` and `reviewext()` is called to update `ext_records` and `students` tables.

However, as there are probably more than one teachers having the right to review external records, it is necessary to keep track of whom has changed the record information. Therefore, for each record in the `ext_records` table, the column `handler` stores the information of the teacher who is the last one to change that record's information.

# Awards generation and overview

When a teacher has logged in as the Administrator (with the Log In ID being "admin"), s/he can gain access to the administrator's menu. One of the functions is to genrate award. When click "Awards Generation" in the "Admin Function" dropdown menu in the topbar, the function `generate()` is called. The function reviews `total_hours` in the `students` table and determine what should be written in the `award` column ("Gold", "Silver", "Bronze", "Merit", or writing nothing at all). ***This process may take a few minutes because the system needs to handle the students' information one by one.***

After that, when choosing each form in the "Records Overview" dropdown menu, the Administrator can review the students' total service hours and corresponding awards.

# Student list exportation

It may be useful to download all students' records as a CSV file for other administrative work in the school. When a teacher has loggin in as the Administrator, s/he can click "Export Student List" in the "Admin Function" dropdown menu in the topbar, the function `export_students()` is called. This function writes the information of `students` table into a CSV file, which is then exported to the user.

# Manage organisations

Another important functionality of this web application is to allow the Administrator to manage organisations. When the user, logged in as Administrator, clicks "Manage Organisations" in the topbar, s/he can view the table of all school organisations. In the table, the Administrator can change the teacher-in-charge of each organisation - allowing another teacher to review the records related to this organisation when necessary.

If a school organisation no longer exists, the Administrator can also change the organisation's "Disabled" information to "Yes". Students will then no longer be able to choose that organisation when entering internal service records.

The above information of changes is POSTed to the `man_org` route. Function `man_org()` is called to update the `organisations` table accordingly.

# Future Development

Currently, this web application contains the functions (`forgetpw()` and `resetpw()`) useful for allowing users to reset their passwords when they are forgotten. However, it involves configuring the system email account, which is not easy to do so without a web host. Therefore, this functionality is currently disabled.

When the email functionalities can be enabled, one important development direction is to allow auto-sending of emails when the teachers changes the information (e.g. status) of students' service records. Students will then be notified easily when their records are endorsed or rejected.

Another important development direction is to allow the Administrator to import CSV files into the database. With this functionality, the Administrator can directly upload new CSV files to update the `students`, `teachers` and `organisations` tables without using another application (e.g. phpLiteAdmin) for handling mass data changes in a new school year.

This is Service Record!