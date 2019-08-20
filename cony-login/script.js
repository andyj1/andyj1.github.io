/* 
 * Login form generation with a responsive character icon (Cony from LINE Friends)
 * ideas from 'Login Critter': https://github.com/cgoldsby/LoginCritter (Swift)
 *           'Ryan': https://github.com/taggon/ryan-login (JS, SVG)
 * **All copyrights pertaining to the image origin are reserved for NAVER Corp.(TM)
 */

"use strict"; // use only declared variables

(function(){

const cony = document.querySelector('#cony');
const face = document.querySelectorAll('.eyes, .muzzle'); 
const ears = document.querySelectorAll('.ears');
const email = document.querySelector('input[type="text"]');
const password = document.querySelector('input[type="password"]');

const newDivElement = document.createElement('div');
const span = document.createElement('span');
let timer = null;

function rotate3d(x, y, z, rad) {
    // rotate3d: built-in CSS DOM transformation function
    const rotation = `rotate3d(${x}, ${y}, ${z}, ${rad}rad)`;
    
    clearTimeout(timer);
    timer = setInterval(function() {
        for (let i=0; i < face.length; i++) {
            face[i].style.transform = rotation;
        }
    }, 100);
}

function focus(event) {
    event.target.classList.add('focused');
    copyStyles(event.target);
    event.target.type === 'password' ? lookAway(event) : look(event);
}

function reset(event) {
    event.target.classList.remove('focused');
    cony.classList.remove('notLooking');
    cony.classList.remove('look');

    clearTimeout(timer);
    timer = setInterval( () => {
        cony.classList.remove('look-away', 'down', 'up');
        rotate3d(0,0,0,0);
    }, 100 );
}

// utility function to copy input styles to a new <div> element
// to calculate the relative location of the filled text in the input field
function copyStyles(element) {
    const props = window.getComputedStyle(element, null);

    if ( newDivElement.parentNode === document.body ) {
        document.body.removeChild(newDivElement);
    }

    newDivElement.style.visibility = 'hidden';
    newDivElement.style.position = 'absolute';
    newDivElement.style.top = Math.min(element.offsetHeight * -2, -999) + 'px';

    // copy the styles
    for(let i=0; i < props.length; i++) {
        if (['visibility','display','opacity','position','top','left','right','bottom'].indexOf(props[i]) !== -1) {
            continue;
        }
        newDivElement.style[props[i]] = props.getPropertyValue(props[i]);
    }

    document.body.appendChild(newDivElement);
}

function translateEars(x, y) {    
    // translate: CSS DOM transformation function in y-direction
    console.log(`${x}, ${y}`)
    const transformation = `translate2d(${x}, ${y})`;
    for (let i = 0; i < ears.length; i++) {
        ears[i].style.transform = transformation;
        console.log(ears[i].style.transform)
    }
}

function look(event) {
    const element = event.target;
    const text = element.value.substr(0, element.selectionStart);

    span.innerText = text || '.';

    const conyRect = cony.getBoundingClientRect();
    const inputRect = element.getBoundingClientRect();
    const caretRect = span.getBoundingClientRect();
    // caretPos count only if there is text > 0
    const caretPos = caretRect.left + Math.min(caretRect.width, inputRect.width) * !! text;
    const distCaret = conyRect.left + conyRect.width/2 - inputRect.left - caretPos;
    const distInput = conyRect.top + conyRect.height/2 - inputRect.top;
    const y_angle = Math.atan2(-distCaret, Math.abs(distInput)*3);
    const x_angle =  Math.atan2(distInput, Math.abs(distInput)*3 / Math.cos(y_angle));
    const theta = Math.max(Math.abs(x_angle), Math.abs(y_angle));
    
    rotate3d(x_angle/theta, y_angle/theta, y_angle/theta, theta);
    
    cony.classList.add('look');
    console.log(cony.classList)
    // translateEars(0,10)
}


function lookAway(event) {
    const el = event.target;
    const conyRect = cony.getBoundingClientRect();
    const inputRect = el.getBoundingClientRect();
    const distInput = conyRect.top + conyRect.height/2 - inputRect.top;
    // console.log("distInput:"+conyRect.top+"/"+ conyRect.height/2 +"/"+  inputRect.top)
    cony.classList.add( 'look-away', distInput < 0 ? 'up' : 'down' );
    
    clearTimeout(timer);
    timer = setInterval(function() {
        cony.classList.add('notLooking');
        console.log(cony.classList)
    }, 100);  

}

newDivElement.appendChild(span);

email.addEventListener( 'focus', focus, false );
email.addEventListener( 'keyup', look, false );
email.addEventListener( 'click', look, false );
email.addEventListener( 'blur', reset, false );

password.addEventListener( 'focus', lookAway, false );
password.addEventListener( 'blur', reset, false );

})();