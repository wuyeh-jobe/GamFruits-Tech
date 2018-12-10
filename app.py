from flask import Flask, render_template, flash,request, redirect, url_for, session, logging,jsonify #pip install flask
#from data import Articles
from flask_mysqldb import MySQL #pip install flask-mysqldb
from wtforms import Form, StringField, TextAreaField, PasswordField, validators #before this works, pip install flask-wtf
from passlib.hash import sha256_crypt #before this works, pip install passlib
from functools import wraps
import datetime


app = Flask(__name__)
#config db
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'gafruitsapp'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

#init MYSQL
mysql = MySQL(app)

#This renders the homepage
@app.route('/')
def index():
    return render_template("index.html")


#Thus logs in the user into the system
@app.route('/login', methods=['POST','GET'])
def login():
    if request.method == 'POST':
        #get for fields
        staff_id = request.form['id']
        password_candidate = request.form['password']

        #create cursor
        cur = mysql.connection.cursor()

        #get user by username
        result = cur.execute('Select * from staff where staff_id = %s', [staff_id])
        
        if result > 0:
            data = cur.fetchone()
            password = data['Password']
            name = data['Name']
            position = data['Position']
            squestion = data['squestion']
            
            #compare passwords
            if password_candidate == password:
                #passed
                session['staff_id'] = staff_id
                if squestion=="":
                    return redirect(url_for("setup"))
                else:
                    session['logged_in'] = True
                    session['name'] = name
                    session['role'] = position
                    flash("You are now logged in",'success')
                    if position == "Farmer":
                        return redirect(url_for('update'))
                    else:
                        return redirect(url_for('wholesale'))
            else:
                error = "Invalid login"
                return render_template('login.html', error=error)

            #close connection
            cur.close()
        else:
            error = "Wrong details"
            return render_template('login.html', error=error)

    return render_template('login.html')


#check if logged_in, not be able to go to a link by changing url in bar
def is_logged_in(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' in session:
            return f(*args, **kwargs)
        else:
            flash('Unauthourized access, please log in', 'danger')
            return redirect('login')
    return wrap

#Route for first time setup
@app.route('/setup',methods=['POST',"GET"])
def setup():
    #create cursor
    cur = mysql.connection.cursor()
    #get user by username
    result = cur.execute('Select * from staff where staff_id = %s', [session['staff_id']])
    data = cur.fetchone()
    staff_id = data['Staff_id']
    name = data['Name']+" "+data['Surename']
    role = data['Position']
    if request.method == "POST":
        password = request.form['password']
        squestion = request.form['squestion']
        sanswer = request.form['sanswer']
        #create cursor
        cur2 = mysql.connection.cursor()
        cur2.execute("Update staff set Password = %s, squestion = %s, sanswer = %s Where Staff_id=%s", 
        (password,squestion,sanswer,staff_id))
        mysql.connection.commit()
        cur2.close()
        flash('Set up complete', 'success')
        return redirect(url_for('login'))
    cur.close()
    return render_template('setup.html',staff_id=staff_id,name=name,role=role)

#Route for forget password
@app.route('/forgotpassword',methods=['POST',"GET"])
def forgotpassword():
    if request.method == "POST":
        if 'staff_id' in session:
            #create cursor
            cur3 = mysql.connection.cursor()
            #get user by username
            result3 = cur3.execute('Select * from staff where staff_id = %s', (session['staff_id'],))
            data = cur3.fetchone()
            sanswer = data['sanswer']
            password = request.form['password']
            sanswer_given = request.form['sanswer']
            if sanswer_given == sanswer:
                #create cursor
                cur2 = mysql.connection.cursor()
                cur2.execute("Update staff set Password = %s Where Staff_id=%s", 
                (password,session['staff_id']))
                mysql.connection.commit()
                cur2.close()
                cur3.close()
                flash('Password Changed', 'success')
                return redirect(url_for('login'))
            else:
                session.clear()
                flash('Security answer provided is wrong', 'danger')
                return redirect(url_for('forgotpassword'))
        else:
            staff_id = request.form['id']
            session['staff_id'] = staff_id
            #create cursor
            cur = mysql.connection.cursor()
            #get user by username
            result = cur.execute('Select * from staff where staff_id = %s', [staff_id])
            if result>0:
                data = cur.fetchone()
                staff_id = data['Staff_id']
                name = data['Name']+" "+data['Surename']
                role = data['Position']
                squestion = data['squestion']
                sanswer = data['sanswer']
                return render_template('forgotpassword.html',staff_id=staff_id,name=name,role=role,squestion=squestion)
            else:
                flash('The Id your provided is wrong', 'danger')
                return redirect(url_for('forgotpassword'))
    return render_template('forgotpassword.html')

#user logout
@app.route('/logout')
@is_logged_in
def logout():
    session.clear()
    flash('You are logged out', 'success')
    return redirect(url_for('login'))

#This renders the wholesale point of sales
@app.route('/wholesale')
@is_logged_in
def wholesale():
    stock_details = uploadstocks('Wholesale')
    messages = uploadmessages("5")
    return render_template('wholesale.html', stock_details=stock_details, messages=messages)

#This renders the retail points of sales
@app.route('/retail')
@is_logged_in
def retail():
    stock_details = uploadstocks('Retail')
    messages = uploadmessages("5")
    return render_template('retail.html', stock_details=stock_details,messages=messages)

#This renders send messages template for sales personnel
@app.route('/smessages',methods=['POST','GET'])
@is_logged_in
def smessages():
    messages = uploadmessages("5")
    if request.method == "POST":
        title = request.form['title']
        message = request.form['editor']
        sendmessage(title,message)
        flash('Message sent to farmers!', 'success')
        if "mtoread" in session:
            del session['mtoread']
        return redirect(url_for('smessages'))
    return render_template('smessages.html',messages=messages)

#This function is for updating stocks
#A list of all the items stored are displayed then users can update
@app.route('/update', methods=['POST','GET'])
@is_logged_in
def update():
    stock_details = []
    messages = uploadmessages("5")
    #create cursor
    cur = mysql.connection.cursor()
    #get all stocks
    result = cur.execute("Select * from stock")
    if result > 0:
        all_data = cur.fetchall()
        for data in all_data:
            name = data['Name']
            quantity = data['Quantity']
            price = data['Price']
            last_updated = data['Last_Updated']
            s_type = data['type']
            iD = data['ID']
            stock_details.append(name + "," + quantity + "," + price 
            + ","+last_updated.isoformat()+ ","+s_type+","+str(iD))
    cur.close()
    #This updates the specific stock that is clicked
    if request.method == "POST":
        name2 = request.form['name']
        quantity2 = request.form['quantity']
        price2 = request.form['price']
        id2 = int(request.form['id'])

        #This gets the details before they are updated
        cur0 = mysql.connection.cursor()
        result = cur0.execute("Select * from stock where ID=%s",[id2])
        qty = "0"
        pr = "0"
        lasup = ""
        if result > 0:
            data0 = cur0.fetchone()
            qty= data0['Quantity']
            pr = data0['Price']
            lasup = data0['Last_Updated'].isoformat()

        #create cursor
        cur2 = mysql.connection.cursor()
        #get all stocks
        current_date = datetime.datetime.now()
        cur2.execute("Update stock set Name = %s, Price = %s, Quantity = %s, Last_Updated = %s Where ID=%s", 
        (name2,price2,quantity2,current_date,id2))
        mysql.connection.commit()
        cur2.close()
        flash(name2+' has been updated', 'success')
        if session['role']=="Sales":
            return redirect(url_for('update'))
        else:
            note = request.form['note']
            sendmessage("Updated "+name2, "Previous ==> Qunatity: "+qty+", Price: "+pr+", Last Updated: "+lasup+
            "  <||>  New ==> Quantity :"+quantity2+", Price: "+price2+", Date :" +current_date.isoformat()+
             "   <||>  Note: "+note)
            flash("A message has been sent to sales. Thanks "+session['name']+"!", 'success')
            return redirect(url_for('update'))
    if session['role']=="Sales":
        return render_template('update.html', stock_details=stock_details,messages=messages)
    else:
        return render_template('fupdate.html', stock_details=stock_details,messages=messages)


#This function deletes a stock from the database
@app.route('/delete', methods=['POST'])
@is_logged_in
def delete():
    if request.method == "POST":
        name = request.form['name']
        id = request.form['id']
        #create cursor
        cur2 = mysql.connection.cursor()
        #get all stocks
        cur2.execute("Delete from stock  Where ID=%s", (id,))
        mysql.connection.commit()
        flash(name+' has been deleted', 'success')
        return redirect(url_for('update'))

#renders the summary template
@app.route('/summary')
@is_logged_in
def summary():
    return render_template('summary.html')

#This function is for adding stocks
@app.route('/addStock', methods=['POST','GET'])
@is_logged_in
def addStock():
    if request.method == "POST":
        name = request.form['name']
        quantity = request.form['quantity']
        price = request.form['price']
        s_type = request.form['select']
        file = request.files['image']
        data= file.read()
        try:
            # prepare update query and data
            query = 'INSERT INTO stock(Name, Quantity, Price, Image, Type) VALUES(%s,%s,%s,%s,%s)'
        
            #use cursor
            cur =  mysql.connection.cursor()
            #execute query
            cur.execute(query,(name,quantity,price,data,s_type))
            #commit DB
            mysql.connection.commit()
            #close connect
            cur.close()
            flash(name+' is added', 'success')
            #Return the appropriate template for each staff
            if session['role'] == 'Sales':
                if s_type == "Retail":
                    return redirect(url_for('retail'))
                else:
                    return redirect(url_for('wholesale'))
            else:
                flash("A message has been sent to sales. Thanks "+session["name"]+"!", 'success')
                sendmessage('Added '+name, "Quantity "+quantity+ "| Price "+price)
                return redirect(url_for('farmer'))
        except:
            error = name + " already exist"
            if session['role'] == 'Sales':
                if s_type == "Retail":
                    return render_template('retail.html', error=error)
                else:
                    return render_template('wholesale.html', error=error)
            else:
                return render_template('farmer.html', error=error)


#upload stock details
def uploadstocks(s_type):
    stock_details = []
    #create cursor
    cur = mysql.connection.cursor()
    #get stocks with the type 'Retail'
    result = cur.execute("Select * from stock where type = %s",[s_type])
    if result > 0:
        all_data = cur.fetchall()
        for data in all_data:
            name = data['Name']
            quantity = data['Quantity']
            price = data['Price']
            s_type = data['type']
            #Read image and name it the name of the image
            read_blob(name, 'static\\img\\' +name+".jpg")
            stock_details.append(name + "(D" +price+ ")," + "img/"+name+".jpg")
    cur.close()
    return stock_details



#Reading and writng Image into database
def write_file(data, filename):
    with open(filename, 'wb') as f:
        f.write(data)

#This function is for reading an image
def read_blob(name, filename):
    #create cursor
    cur = mysql.connection.cursor()
    #get user by username
    result = cur.execute('Select * from stock where Name = %s', [name])
    if result > 0:
        data = cur.fetchone()
        photo = data['Image']
        # write blob data into a file
        write_file(photo, filename)
        cur.close()
        return filename

#This renders the farmer template
@app.route('/farmer')
@is_logged_in
def farmer():
    messages = uploadmessages("5")
    return render_template('farmer.html', messages=messages)

#This renders and sends message by farmer
@app.route('/fmessages', methods=['POST','GET'])
@is_logged_in
def fmessages():
    messages = uploadmessages("5")
    if request.method == "POST":
        title = request.form['title']
        message = request.form['editor']
        sendmessage(title,message)
        flash('Message sent!', 'success')
        if "mtoread" in session:
            del session['mtoread']
        return redirect(url_for('fmessages'))
    return render_template('fmessages.html',messages=messages)

#This is helper function to send the messages
def sendmessage(title,message):
    try:
        # prepare update query and data
        query = 'INSERT INTO message(staff_id, title,message) VALUES(%s,%s,%s)'
        
        #use cursor
        cur =  mysql.connection.cursor()
        #execute query
        cur.execute(query,(session['staff_id'],title,message))
        #commit DB
        mysql.connection.commit()
        #close connect
        cur.close()
    except:
        print("Something")


#This function show the messages from the database
def uploadmessages(n):
    messages = []
    #create cursor
    cur = mysql.connection.cursor()
    result = 0
    if n == "all":
        result = cur.execute("Select * from message Order By id DESC")
    else:
        #get five stocks to display for message dialogue
        result = cur.execute("Select * from message Order By id DESC limit 5")
    
    if result > 0:
        all_data = cur.fetchall()
        for data in all_data:
            id = data['id']
            staff_id = data['staff_id']
            title = data['title']
            message= data['message']
            time = data['time']
            #Get staff details using foreign key in messages
            cur0 = mysql.connection.cursor()
            result2 = cur0.execute("Select * from staff where Staff_id = %s",[staff_id])
            name = ""
            role = ""
            
            if result2>0:
                staff_data = cur0.fetchone()
                name = staff_data['Name'] + " "+ staff_data['Surename']
                role = staff_data['Position']
            #td = datetime.datetime.now().date().isoformat()
            #if td == time.date().isoformat():
            messages.append(name+"#"+role+"#"+title+"#"+message+"#"+time.date().isoformat()+" "+
            time.strftime ('%H:%M')+"#"+time.date().isoformat()+"#"+str(id))
    cur.close()
    return messages

#read for message sales
@app.route('/readmessage/<string:id>')
@is_logged_in
def readmessage(id):
    messages = uploadmessages("all")
    mtoread = ""
    for message in messages:
        if message.split("#")[6] == id:
            mtoread = message
            session['mtoread'] = message.split("#")[2]
    return render_template('readmessage.html',mtoread=mtoread,messages=messages)

#read for farmers message
@app.route('/freadmessage/<string:id>')
@is_logged_in
def freadmessage(id):
    messages = uploadmessages("all")
    mtoread = ""
    for message in messages:
        if message.split("#")[6] == id:
            mtoread = message
            session['mtoread'] = message.split("#")[2]
    return render_template('freadmessage.html',mtoread=mtoread,messages=messages)

@app.route('/allmessages')
@is_logged_in
def allmessages():
    messages = uploadmessages("5")
    allmessages = uploadmessages("all")
    return render_template('allmessages.html',messages=messages, allmessages=allmessages)

@app.route('/fallmessages')
@is_logged_in
def fallmessages():
    messages = uploadmessages("5")
    allmessages = uploadmessages("all")
    return render_template('fallmessages.html',messages=messages, allmessages=allmessages)




if __name__ == '__main__':
    app.secret_key = "114455"
    app.run(debug=True)
