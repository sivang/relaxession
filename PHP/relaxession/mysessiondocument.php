<?
class mySessionDocument extends phpillowDocument
    {
        protected static $type = 'sess';
 
        protected $requiredProperties = array(
            'session_id',
            'timestamp',
            'session_data',
        );
 
        public function __construct()
        {
            $this->properties = array(
                'session_id'     => new phpillowNoValidator(),
                'timestamp'      => new phpillowNoValidator(),
                'session_data'  => new phpillowNoValidator(),
            );
 
            parent::__construct();
        }
 
        protected function generateId()
        {
            return $this->stringToId( $this->storage->session_id );
        }

        protected function getType()
        {
            return self::$type;
        }
    }

?>
