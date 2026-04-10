
********************************************************************************
* Save ICE arrests so as to identify *interior* removals
********************************************************************************

* arrests (to identify interior arrests)
import delimited "arrests-latest.csv", varnames(1) clear 
keep unique_identifier
duplicates drop /* This isn't QUITE right because a person could be arrested after a border deportation? But that'll be a tiny fraction */
rename unique_identifier anonymizedidentifier
gen inarrestsdata = 1
tempfile arrestees 
save `arrestees' 


********************************************************************************
* Calculate number of detained Venezuelans
********************************************************************************

* Latest DDP data
use "detention-stays-latest.dta", clear

* keep Venezuelans arrested by ICE and drop all others
keep if citizenship_country == "VENEZUELA"
rename unique_identifier anonymizedidentifier
merge m:1 anonymizedidentifier using `arrestees' 
drop if _m == 2
	/* Check that this is doing what we want — looks good
	tab book_in_criminality if _m == 1
	tab book_in_criminality if _m == 3
	tab final_program if _m == 1
	tab final_program if _m == 3 */
drop if _m == 1 /* Border detainees */ 

* calculate days for last stay and total time
gen int bookindate = dofC(stay_book_in_date_time)
rename stay_book_out_date bookoutdate
format bookindate bookoutdate 

* NOTE: could/should get Venezuelans booked in before 2022
* BUT basically none of these people will still be detained in 2024

* fake release date for people still detained
gen bookoutdate2 = bookoutdate
replace bookoutdate2 = daily("10apr2026","DMY") if missing(bookoutdate)
format bookoutdate2 %td

* save number of entries per day
preserve
gen entries = 1
collapse (sum) entries, by(bookindate)
rename bookindate date
tempfile entries 
save `entries'
restore 

* save number of exits per day
gen exits = 1 
collapse (sum) exits, by(bookoutdate2)

* merge entries
rename bookoutdate date
merge 1:1 date using `entries'
replace entries = 0 if entries == .
replace exits = 0 if exits == .

* calculate
gen change = entries - exits
sort date
gen stock = sum(change)


********************************************************************************
* Graph
********************************************************************************

* graph
twoway line stock date if date >= td(01sep2024) & date <= td(10mar2026), ///
   xline(`=td(03jan2026)')


********************************************************************************
* End of do file
********************************************************************************
