<?php

session_start();

if (isset($_SESSION['LAST_ACTIVITY']) && (time() - $_SESSION['LAST_ACTIVITY'] > 1800)) { // 30 minutes
    session_unset();
    session_destroy();
    session_start();
    $_SESSION['step'] = 'language';
}
$_SESSION['LAST_ACTIVITY'] = time();

if (!isset($_SESSION['step'])) {
    $_SESSION['step'] = 'language';
}

header("Access-Control-Allow-Credentials: true");
header("Access-Control-Allow-Origin: http://127.0.0.1:5500");
header("Access-Control-Allow-Methods: POST");
header("Access-Control-Allow-Headers: Content-Type");
header("Content-Type: text/html; charset=UTF-8");


// MAPS
$banks = [
    '1' => 'Habib Bank Limited',
    '2' => 'United Bank Limited',
    '3' => 'Allied Bank Limited',
    '4' => 'Meezan Bank',
    '5' => 'Bank Alfalah',
    '6' => 'MCB Bank',
    '7' => 'Askari Bank',
    '8' => 'Faysal Bank',
    '9' => 'Standard Chartered'
];

$complaintTypes = [
    '1' => 'Delay in receiving remittance',
    '2' => 'Remittance not credited',
    '3' => 'Wrong amount received',
    '4' => 'Wrong beneficiary details',
    '5' => 'Exchange rate issue',
    '6' => 'Deduction without reason',
    '7' => 'No alert received',
    '8' => 'Remittance held/blockage',
    '9' => 'Remittance rejected',
    '10' => 'Other'
];

function remove_spaces_in_numbers($text)
{
    return preg_replace('/(?<=\d) (?=\d)/', '', $text);
}

function call_python_api($endpoint, $data)
{
    $url = "http://127.0.0.1:8000/$endpoint"; // Change to your FastAPI URL

    $payload = json_encode($data);

    $ch = curl_init($url);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, $payload);
    curl_setopt($ch, CURLOPT_HTTPHEADER, [
        'Content-Type: application/json',
        'Content-Length: ' . strlen($payload)
    ]);

    $response = curl_exec($ch);
    if ($response === false) {
        echo "Curl error: " . curl_error($ch);
        return null;
    }

    curl_close($ch);

    return json_decode($response, true);
}

function validate($field, $input)
{
    switch ($field) {
        case 'name':
            return preg_match("/^[a-zA-Z\s]{2,}$/u", $input);
        case 'cnic':
            return preg_match("/^(\d{5}-\d{7}-\d{1}|\d{13})$/", $input);

        case 'phone':
            return preg_match("/^(03[0-9]{9}|00923[0-9]{9}|\+923[0-9]{9})$/", $input);
        case 'email':
            return filter_var($input, FILTER_VALIDATE_EMAIL);
        default:
            return false;
    }
}

if ($_SERVER["REQUEST_METHOD"] == 'GET') {
    echo $_SESSION['lang'];
}

if ($_SERVER['REQUEST_METHOD'] == 'POST') {

    $route = $_GET['route'] ?? '';

    if ($route === "confirm") {


        // Update session with user-edited data
        $_SESSION['name'] = $_POST['name'];
        $_SESSION['phone'] = $_POST['phone'];
        $_SESSION['cnic'] = $_POST['cnic'];
        $_SESSION['email'] = $_POST['email'];
        $_SESSION['bank'] = $_POST['bank'];
        $_SESSION['complaint_type'] = $_POST['complaint_type'];
        $_SESSION['description'] = $_POST['description'];

        $conn = new mysqli("localhost", "root", "", "complaint_management_db");
        if ($conn->connect_error) {
            echo "DB Error: " . $conn->connect_error;
            exit;
        }

        $stmt = $conn->prepare("SELECT ID FROM user_details WHERE CNIC = ?");
        $stmt->bind_param("s", $cnic);
        $stmt->execute();
        $result = $stmt->get_result();
        if ($row = $result->fetch_assoc()) {
            // Update existing
            $user_id = $row['ID'];
            $stmt2 = $conn->prepare("UPDATE user_details SET Full_Name=?, Phone_No=?, Email=? WHERE ID=?");
            $stmt2->bind_param("sssi", $_SESSION["name"], $_SESSION["phone"], $_SESSION["email"], $user_id);
            $stmt2->execute();
            $stmt2->close();
        } else {
            // Insert new
            $stmt2 = $conn->prepare("INSERT INTO user_details (Full_Name, Phone_No, CNIC, Email) VALUES (?, ?, ?, ?)");
            $stmt2->bind_param("ssss", $_SESSION["name"], $_SESSION["phone"], $_SESSION["cnic"], $_SESSION["email"]);
            $stmt2->execute();
            $user_id = $stmt2->insert_id;
            $stmt2->close();
        }
        $stmt->close();



        $stmt = $conn->prepare("INSERT INTO complaint_details (Bank_Name, Complaint_Type, Complaint_Desc, User_ID) VALUES (?, ?, ?, ?)");
        $stmt->bind_param("sssi", $_SESSION['bank'], $_SESSION['complaint_type'], $_SESSION['description'], $user_id);
        $stmt->execute();
        $stmt->close();


        
        require_once(__DIR__ . '/phpqrcode/qrlib.php');
        $qrDir = "C:/xampp/htdocs/backend/qrcodes/";
        if (!file_exists($qrDir))
            mkdir($qrDir, 0777, true);

         $qrData = json_encode([
                'name' => $_SESSION["name"],
                'phone' => $_SESSION["phone"],
                'cnic' => $_SESSION["cnic"],
                'email' => $_SESSION["email"],
                'bank' => $_SESSION["bank"],
                'complaint_type' => ["complaint_type"],
                'description' => ["description"],
                'timestamp' => date('c')
            ], JSON_UNESCAPED_UNICODE);
       
        $qrFileName = 'complaint_' . time() . '_' . rand(1000, 9999) . '.png';
        $qrFileRel = 'qrcodes/' . $qrFileName;
        $qrFileAbs = $qrDir . $qrFileName;

        QRcode::png($qrData, $qrFileAbs, QR_ECLEVEL_H, 6);
            $imgTag = "<br><img src='$qrFileRel' alt='Complaint QR Code' style='width:200px;'><br>" .
                "<a href='$qrFileRel' download='complaint_qr.png'>Download QR Code</a>";
            echo "Thank you. Your complaint has been registered." . $imgTag;

        session_destroy();

        echo "Thank you. Your complaint has been registered." . $imgTag;

        exit;
    }

    $msg = $_POST['message'] ?? '';
    $input = trim($msg);



    if ($route === 'bot') {


        $info = $input ?? '';


        // SESSION DEFAULTS
        $_SESSION['remaining_fields'] = $_SESSION['remaining_fields'] ?? [
            "name" => null,
            "cnic" => null,
            "phone" => null,
            "bank" => null,
            "email" => null,
            "complaint_type" => null,
            "description" => null,
            "is_registered_user" => null
        ];

        $_SESSION['previous_question'] = $_SESSION['previous_question'] ?? "";

        if (
            isset($_SESSION['remaining_fields']['is_registered_user'])
            & $_SESSION['remaining_fields']['is_registered_user'] == "True"
            & isset($_SESSION['remaining_fields']['cnic'])
            & $_SESSION['remaining_fields']['name'] == "already provided"
        ) {

            $conn = new mysqli("localhost", "root", "", "complaint_management_db");
            if ($conn->connect_error) {
                echo "DB Error: " . $conn->connect_error;
                exit;
            }

            $stmt = $conn->prepare("SELECT Full_Name, Phone_No, Email FROM user_details WHERE CNIC = ?");
            $stmt->bind_param("s", $cnic);
            $stmt->execute();
            $result = $stmt->get_result();
            if ($row = $result->fetch_assoc()) {

                $_SESSION['remaining_fields']['name'] = $row['Full_Name'];
                $_SESSION['remaining_fields']['phone'] = $row['Phone_No'];
                $_SESSION['remaining_fields']['email'] = $row['Email'];

            }
        }
        // Prepare payload for Python
        $payload = [
            "info" => $info,
            "remaining_fields" => $_SESSION['remaining_fields'],
            "previous_question" => $_SESSION['previous_question']
        ];

        // Send to FastAPI
        $botResponse = call_python_api('bot/', $payload);

        // Update SESSION state
        if (isset($botResponse['state'])) {
            $_SESSION['remaining_fields'] = $botResponse['state'];
        }
        if (isset($botResponse['message'])) {
            $_SESSION['previous_question'] = $botResponse['message'];
        }

        if ($botResponse['message'] == "complain has been finalized") {
            $conn = new mysqli("localhost", "root", "", "complaint_management_db");
            if ($conn->connect_error) {
                echo "DB Error: " . $conn->connect_error;
                exit;
            }

            $stmt = $conn->prepare("SELECT CNIC FROM user_details WHERE CNIC = ?");
            $stmt->bind_param("s", $cnic);
            $stmt->execute();
            $result = $stmt->get_result();
            if ($row = $result->fetch_assoc()) {
                // Update existing
                $user_id = $row['CNIC'];
                $stmt2 = $conn->prepare("UPDATE user_details SET Full_Name=?, Phone_No=?, Email=? WHERE CNIC=?");
                $stmt2->bind_param("ssss", $_SESSION['name'], $_SESSION['phone'], $_SESSION['email'], $user_id);
                $stmt2->execute();
                $stmt2->close();
            } else {
                // Insert new
                $stmt2 = $conn->prepare("INSERT INTO user_details (Full_Name, Phone_No, CNIC, Email) VALUES (?, ?, ?, ?)");
                $stmt2->bind_param("ssss", $_SESSION['name'], $_SESSION['phone'], $_SESSION['cnic'], $_SESSION['email']);
                $stmt2->execute();
                $user_id = $stmt2->insert_id;
                $stmt2->close();
            }
            $stmt->close();



            $stmt = $conn->prepare("INSERT INTO complaint_details (Bank_Name, Complaint_Type, Complaint_Desc, User_ID) VALUES (?, ?, ?, ?)");
            $stmt->bind_param("sssi", $_SESSION['bank'], $_SESSION['complaint_type'], $_SESSION['description'], $user_id);
            $stmt->execute();
            $stmt->close();

            require_once(__DIR__ . '/phpqrcode/qrlib.php');
            $qrDir = "C:/xampp/htdocs/backend/qrcodes/";
            if (!file_exists($qrDir))
                mkdir($qrDir, 0777, true);

            $qrData = json_encode([
                'name' => $_SESSION['remaining_fields']["name"],
                'phone' => $_SESSION['remaining_fields']["phone"],
                'cnic' => $_SESSION['remaining_fields']["cnic"],
                'email' => $_SESSION['remaining_fields']["email"],
                'bank' => $_SESSION['remaining_fields']["bank"],
                'complaint_type' => $_SESSION['remaining_fields']["complaint_type"],
                'description' => $_SESSION['remaining_fields']["description"],
                'timestamp' => date('c')
            ], JSON_UNESCAPED_UNICODE);
            $qrFileName = 'complaint_' . time() . '_' . rand(1000, 9999) . '.png';
            $qrFileRel = 'qrcodes/' . $qrFileName;
            $qrFileAbs = $qrDir . '/' . $qrFileName;
            QRcode::png($qrData, $qrFileAbs, QR_ECLEVEL_H, 6);
            $imgTag = "<br><img src='$qrFileRel' alt='Complaint QR Code' style='width:200px;'><br>" .
                "<a href='$qrFileRel' download='complaint_qr.png'>Download QR Code</a>";
            echo "Thank you. Your complaint has been registered." . $imgTag;
            exit;

        }

        $allFieldsFilled = true;
        foreach ($_SESSION['remaining_fields'] as $field => $value) {
            if ($value === null || trim($value) === 'unknown' || trim($value) === '') {
                $allFieldsFilled = false;
                break;
            }
        }

        if ($allFieldsFilled) {
            // Return JSON response with confirmation data
            $confirmationData = [
                'showConfirmation' => true,
                'data' => $_SESSION['remaining_fields'],
                'message' => $botResponse['message'],
            ];
            echo json_encode($confirmationData);
            exit;

        }
        echo json_encode($botResponse['message']);
        exit;

    } else if ($route === 'kill') {

        session_destroy();
        if (ini_get("session.use_cookies")) {
            setcookie(session_name(), '', time() - 42000, '/');
        }

        echo "true";
        exit;
    } else {



        $step = $_SESSION['step'];
        switch ($step) {

            case 'language':
                if ($msg == "2") {
                    $_SESSION['lang'] = 'ur';
                    $_SESSION['step'] = 'cnic';
                    echo "زبان منتخب کی گئی: اُردو۔ براہِ کرم اپنا شناختی کارڈ نمبر بتائیں؟";
                } else if ($msg == "1") {
                    $_SESSION['lang'] = 'en';
                    $_SESSION['step'] = 'cnic';
                    echo "Language selected: English. <br>Please enter your cnic.";
                } else {
                    echo "Invalid selection. Please type 1 for English or 2 for Urdu.";
                }
                break;

            case 'name':
                // Step 1: Call FastAPI to extract the name
                $input = str_replace("-", "", $input);

                if ($_SESSION['lang'] === 'ur') {
                    if(!preg_match('/[a-zA-Z]/', $input)){

                        $nameDetails =  call_python_api("extract-name-urdu/", ["info" => $input]);

                    }else{

                        $input = call_python_api("translate/", ["info" => $input]);
                        $nameDetails = call_python_api("extract-name/", ["info" => strtolower($input)]);

                    }

                if (!$nameDetails) {
                    echo $_SESSION['lang'] === 'ur'
                        ? "مہربانی فرما کر اپنا صحیح نام درج کریں۔"
                        : "Please enter a valid name.";
                    break;
                }

                    
                  
                }else{
                
                $nameDetails = call_python_api("extract-name/", ["info" => strtolower($input)]);

                // Step 2: Check if name was extracted successfully
                if (!$nameDetails) {
                    echo $_SESSION['lang'] === 'ur'
                        ? "مہربانی فرما کر اپنا صحیح نام درج کریں۔"
                        : "Please enter a valid name.";
                    break;
                }


                }
                // Step 3: Save and go to next step
                $_SESSION['name'] = $nameDetails;
                $_SESSION['step'] = 'phone';
                echo $_SESSION['lang'] === 'ur'
                    ? "موبائل نمبر درج کریں (مثال: 03001234567)"
                    : "Enter your Phone Number (03xxxxxxxxx).";
                break;

               

           case 'phone':


                if ($_SESSION['lang'] === 'ur') {
                    $input = call_python_api("translate/", ["info" => $input]);
                }

                $input = remove_spaces_in_numbers($input);
                $input = str_replace("-", "", $input);
                $input = str_replace(".", "", $input);
                $input = str_replace(",", "", $input);


                $phoneDetails = call_python_api("extract-phone/", ["info" => $input]);
                if (!$phoneDetails || !validate('phone', $phoneDetails)) {
                    echo $_SESSION['lang'] === 'ur'
                        ? "براہِ کرم درست موبائل نمبر درج کریں (مثال: 03001234567)"
                        : "Enter a valid phone name.";
                    break;
                }
                $_SESSION['phone'] = $phoneDetails;
                $_SESSION['step'] = 'email';
                echo $_SESSION['lang'] === 'ur'
                    ? "(example@example.com کی صورت میں) براہِ کرم اپنا ای میل ایڈریس درج کریں"
                    : "Enter your email address.";
                break;

            case 'cnic':

                if ($_SESSION['lang'] === 'ur') {
                    $input = call_python_api("translate/", ["info" => $input]);
                }

                $input = remove_spaces_in_numbers($input);
                $input = str_replace("-", "", $input);
                $input = str_replace(".", "", $input);
                $input = str_replace(",", "", $input);
                $cnicDetails = call_python_api("extract-cnic/", ["info" => $input]);
                if (!$cnicDetails || !validate('cnic', $cnicDetails)) {
                    echo $_SESSION['lang'] === 'ur'
                        ? ". (XXXXX-XXXXXXX-X)CNIC فارمیٹ میں نمبر درج کریں درست"
                        : "Enter valid cnic required format is XXXXX-XXXXXXX-X.";
                    break;
                }
                // Check if CNIC exists in DB
                $conn = new mysqli("localhost", "root", "", "complaint_management_db");
                if ($conn->connect_error) {
                    echo $conn->connect_error;
                    die("DB Connection failed");
                }
                $stmt = $conn->prepare("SELECT ID, Full_Name, Phone_No, Email FROM user_details WHERE CNIC = ?");
                $stmt->bind_param("s", $cnicDetails);
                $stmt->execute();
                $result = $stmt->get_result();
                if ($row = $result->fetch_assoc()) {
                    // CNIC exists, show details and ask for action
                    $_SESSION['cnic'] = $cnicDetails;
                    $_SESSION['existing_user'] = $row['ID'];
                    $_SESSION['existing_user_details'] = $row;
                    $_SESSION['step'] = 'cnic_exists_action';
                    $details = ($_SESSION['lang'] === 'ur')
                        ? "پہلے سے موجود تفصیلات:<br>نام: {$row['Full_Name']}<br>فون: {$row['Phone_No']}<br>ای میل: {$row['Email']}<br>کیا آپ انہی تفصیلات کو استعمال کرنا چاہتے ہیں؟<br>1: جی ہاں<br>2: نئی تفصیلات درج کریں"
                        : "Existing details found:<br>Name: {$row['Full_Name']}<br>Phone: {$row['Phone_No']}<br>Email: {$row['Email']}<br>Do you want to use these details?<br>1: Yes<br>2: Enter new details";
                    echo $details;
                    $stmt->close();
                    $conn->close();
                    break;
                }
                $stmt->close();
                $conn->close();
                // If not exists, proceed as normal
                $_SESSION['cnic'] = $cnicDetails;
                $_SESSION['step'] = 'name';
                echo $_SESSION['lang'] === 'ur'
                    ? "براہِ کرم اپنا نام بتائیں؟"
                    : "Please enter your full name.";
                break;
            case 'cnic_exists_action':
                if ($msg == '1') {
                    // Use existing details
                    $row = $_SESSION['existing_user_details'];
                    $_SESSION['name'] = $row['Full_Name'];
                    $_SESSION['phone'] = $row['Phone_No'];
                    $_SESSION['email'] = $row['Email'];
                    $_SESSION['use_existing_user'] = true;
                    $_SESSION['step'] = 'bank';
                    $menu = "";
                    foreach ($banks as $key => $val) {
                        $menu .= "$key. $val<br>";
                    }
                    echo $_SESSION['lang'] === 'ur'
                        ? "براہ کرم بینک منتخب کریں:<br>$menu"
                        : "Please select your bank:<br>$menu";
                } else if ($msg == '2') {
                    // Enter new details
                    $_SESSION['use_existing_user'] = false;
                    $_SESSION['step'] = 'name';
                    echo $_SESSION['lang'] === 'ur'
                        ? "براہِ کرم اپنا نام بتائیں؟"
                        : "Please enter your full name.";
                } else {
                    echo $_SESSION['lang'] === 'ur'
                        ? "براہ کرم 1 یا 2 میں سے کوئی ایک انتخاب کریں۔"
                        : "Please select 1 or 2.";
                }
                break;

            case 'email':

                if ($_SESSION['lang'] === 'ur') {
                    $input = call_python_api("translate/", ["info" => $input]);
                }
                $input = str_replace([" at ", " dot "], ["@", "."], $input);

                $wordsToNumbers = [
                    "zero" => "0",
                    "one" => "1",
                    "two" => "2",
                    "three" => "3",
                    "four" => "4",
                    "five" => "5",
                    "six" => "6",
                    "seven" => "7",
                    "eight" => "8",
                    "nine" => "9"
                ];
                $input = remove_spaces_in_numbers($input);
                $input = str_replace("-", "", $input);
                $input = str_replace(",", "", $input);
                foreach ($wordsToNumbers as $word => $digit) {
                    $input = str_replace($word, $digit, $input);
                }
                $emailDetails = call_python_api("extract-email/", ["info" => $input]);
                if (!$emailDetails || !validate('email', $emailDetails)) {
                    echo $_SESSION['lang'] === 'ur'
                        ? "درست ای میل درج کریں۔"
                        : "Enter a valid email address.";
                    break;
                }
                $_SESSION['email'] = $emailDetails;
                $_SESSION['step'] = 'bank';
                $menu = "";
                foreach ($banks as $key => $val) {
                    $menu .= "$key. $val<br>";
                }
                echo $_SESSION['lang'] === 'ur'
                    ? "براہ کرم بینک منتخب کریں:<br>$menu"
                    : "Please select your bank:<br>$menu";
                break;

            case 'bank':
                if ($_SESSION['lang'] === 'ur') {
                    $input = call_python_api("translate/", ["info" => $input]);
                }
                $wordsToNumbers = [
                    "zero" => "0",
                    "one" => "1",
                    "two" => "2",
                    "three" => "3",
                    "four" => "4",
                    "five" => "5",
                    "six" => "6",
                    "seven" => "7",
                    "eight" => "8",
                    "nine" => "9",
                    "ten" => "10"
                ];
                foreach ($wordsToNumbers as $word => $digit) {
                    $input = str_replace($word, $digit, strtolower($input));
                }
                $input = remove_spaces_in_numbers($input);
                $input = str_replace("-", "", $input);
                $input = str_replace(".", "", $input);
                $input = str_replace(",", "", $input);

                if (!isset($banks[$input])) {
                    echo $_SESSION['lang'] === 'ur' ? "درست بینک نمبر منتخب کریں (1-9)."
                        : "Please select a valid bank number (1–9).";
                    break;
                }
                $_SESSION['bank_name'] = $banks[$input];
                $_SESSION['step'] = 'complaint';
                $menu = "";
                foreach ($complaintTypes as $key => $val) {
                    $menu .= "$key. $val<br>";
                }
                echo $_SESSION['lang'] === 'ur' ? "براہِ کرم شکایت کی قسم منتخب کریں:<br>$menu"
                    : "Please select complaint type:<br>$menu";
                break;

            case 'complaint':
                if ($_SESSION['lang'] === 'ur') {
                    $input = call_python_api("translate/", ["info" => $input]);
                }
                $wordsToNumbers = [
                    "zero" => "0",
                    "one" => "1",
                    "two" => "2",
                    "three" => "3",
                    "four" => "4",
                    "five" => "5",
                    "six" => "6",
                    "seven" => "7",
                    "eight" => "8",
                    "nine" => "9",
                    "ten" => "10"
                ];
                foreach ($wordsToNumbers as $word => $digit) {
                    $input = str_replace($word, $digit, strtolower($input));
                }
                $input = remove_spaces_in_numbers($input);
                $input = str_replace("-", "", $input);
                $input = str_replace(".", "", $input);
                if (!isset($complaintTypes[$input])) {
                    echo $_SESSION['lang'] === 'ur' ? "درست شکایت نمبر منتخب کریں۔"
                        : "Please choose a valid complaint number.";
                    break;
                }
                if ($input === "10") {
                    $_SESSION['step'] = 'custom_complaint';
                    echo $_SESSION['lang'] === 'ur' ? "براہِ کرم اپنی شکایت درج کریں۔"
                        : "Please specify your complaint.";
                } else {
                    $_SESSION['complaint'] = $complaintTypes[$input];
                    $_SESSION['step'] = 'complain_description';
                    echo $_SESSION['lang'] === 'ur' ? "شکایت کی تفصیل درج کریں۔"
                        : "Enter complaint description.";
                }
                break;

            case 'custom_complaint':
                if ($_SESSION['lang'] === 'ur') {
                    $input = call_python_api("translate/", ["info" => $input]);
                }

                $_SESSION['complaint'] = $input;
                $_SESSION['step'] = 'complain_description';
                echo $_SESSION['lang'] === 'ur' ? "شکایت کی تفصیل درج کریں۔"
                    : "Enter complaint description.";
                break;

            case 'complain_description':

                if (strlen($input) < 5) {
                    echo $_SESSION['lang'] === 'ur' ? "براہِ کرم مکمل شکایت درج کریں۔" : "Please enter a detailed complaint.";
                    break;
                }

                if ($_SESSION['lang'] === 'ur') {
                    $input = call_python_api("translate/", ["info" => $input]);
                }

                if (strlen($input) > 50) {
                    $input = call_python_api("summary/", ["complain" => $input]);
                }

                $_SESSION['complaint_description'] = $input;

                // Return JSON object with current session data
                $reviewData = [
                    'name' => $_SESSION['name'],
                    'phone' => $_SESSION['phone'],
                    'cnic' => $_SESSION['cnic'],
                    'email' => $_SESSION['email'],
                    'bank' => $_SESSION['bank_name'],
                    'complaintType' => $_SESSION['complaint'],
                    'complaintDescription' => $_SESSION['complaint_description']
                ];
                $_SESSION['step'] = "store";
                header('Content-Type: application/json');
                echo "Review" . json_encode($reviewData);
                break;

            case "store":
                $_SESSION['name'] = $_POST['name'] ?? '';
                $_SESSION['phone'] = $_POST['phone'] ?? '';
                $_SESSION['cnic'] = $_POST['cnic'] ?? '';
                $_SESSION['email'] = $_POST['email'] ?? '';
                $_SESSION['bank_name'] = $_POST['bank'] ?? '';
                $_SESSION['complaint'] = $_POST['complaintType'] ?? '';
                $_SESSION['complaint_description'] = $_POST['complaintDescription'] ?? '';



                $conn = new mysqli("localhost", "root", "", "complaint_management_db");
                if ($conn->connect_error) {
                    echo "DB Error: " . $conn->connect_error;
                    exit;
                }
                 $stmt = $conn->prepare("SELECT ID FROM user_details WHERE CNIC = ?");
                $stmt->bind_param("s", $cnic);
                $stmt->execute();
                $result = $stmt->get_result();
                if ($row = $result->fetch_assoc()) {
                    // Update existing
                    $user_id = $row['ID'];
                    $stmt2 = $conn->prepare("UPDATE user_details SET Full_Name=?, Phone_No=?, Email=? WHERE ID=?");
                    $stmt2->bind_param("sssi", $_SESSION['name'], $_SESSION['phone'], $_SESSION['email'], $user_id);
                    $stmt2->execute();
                    $stmt2->close();
                } else {
                    // Insert new
                    $stmt2 = $conn->prepare("INSERT INTO user_details (Full_Name, Phone_No, CNIC, Email) VALUES (?, ?, ?, ?)");
                    $stmt2->bind_param("ssss", $_SESSION['name'], $_SESSION['phone'], $_SESSION['cnic'], $_SESSION['email']);
                    $stmt2->execute();
                    $user_id = $stmt2->insert_id;
                    $stmt2->close();
                }
                $stmt->close();



                $stmt = $conn->prepare("INSERT INTO complaint_details (Bank_Name, Complaint_Type, Complaint_Desc, User_ID) VALUES (?, ?, ?, ?)");
                $stmt->bind_param("sssi", $_SESSION['bank_name'], $_SESSION['complaint'], $_SESSION['complaint_description'], $user_id);

                $stmt->execute();
                $stmt->close();


                require_once(__DIR__ . '/phpqrcode/qrlib.php');
                $qrDir = "C:/xampp/htdocs/backend/qrcodes/";
                if (!file_exists($qrDir))
                    mkdir($qrDir, 0777, true);

                $qrData = json_encode([
                    'name' => $_SESSION['name'],
                    'phone' => $_SESSION['phone'],
                    'cnic' => $_SESSION['cnic'],
                    'email' => $_SESSION['email'],
                    'bank' => $_SESSION['bank_name'],
                    'complaintType' => $_SESSION['complaint'],
                    'complaintDescription' => $_SESSION['complaint_description'],
                    'timestamp' => date('c')
                ], JSON_UNESCAPED_UNICODE);

                $qrFileName = 'complaint_' . time() . '_' . rand(1000, 9999) . '.png';
                $qrFileRel = 'qrcodes/' . $qrFileName;
                $qrFileAbs = $qrDir . $qrFileName;

                QRcode::png($qrData, $qrFileAbs, QR_ECLEVEL_H, 6);
                $imgTag = "<br><img src='http://localhost/backend/qrcodes/$qrFileName' alt='Complaint QR Code' style='width:200px;'><br>" .
                    "<a href='http://localhost/backend/qrcodes/$qrFileName' download='complaint_qr.png'>Download QR Code</a>";

                session_destroy();

                echo ($_SESSION['lang'] === 'ur'
                    ? "شکریہ، آپ کی شکایت درج ہو گئی ہے۔"
                    : "Thank you. Your complaint has been registered.") . $imgTag;

                exit;



            default:
                echo "Something went wrong. Please start again.";
                session_destroy();
                break;
        }

    }
}

?>